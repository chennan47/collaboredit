# -*- coding: utf-8 -*-
"""
    Simple sockjs-tornado chat application. By default will listen on port 8080.
"""
import tornado.ioloop
import tornado.web
import json
import sockjs.tornado
from collections import namedtuple
import time
import json
from uuid import uuid4
import urllib

Cursor = namedtuple('Cursor', ('row', 'column'))

users = []

#help function to insert a string into certain position of another string
def insert(original, new, pos):
    return original[:pos] + new + original[pos:]


#the function to take delta object to form or modify the client text verson
def delta_change_apply(client_text, delta):

    #load the message
    change=json.loads(delta)

    #load the action of the message
    action=change['action']

    #load the range of the message
    range=change['range']

    #load the start aspect of the range object
    start=range['start']

    #load the end aspect of the range object
    end=range['end']

    #load the row aspect of the start object
    start_row=int(start['row'])

    #load the row aspect of the end object
    end_row=int(end['row'])

    #load the column aspect of the start object
    start_column=int(start['column'])

    #load the column aspect of the end object
    end_column=int(end['column'])

    # load the client text and decode it into a string and split it by the newline into a list of string
    text_to_string=json.JSONDecoder(strict=False).decode(client_text).split('\n')

    # deal with the insertText action
    if (action=='insertText'):

        #load the typein text
        type_in=change['text']

        #deal with the text when it is a new line insertion
        if (type_in=='\n'):

            #get the string where the insertion newline happened
            change_string=text_to_string[start_row]

            #break the string into two new string according to the column the insertion happens
            first_part=change_string[:start_column]
            second_part=change_string[start_column:]

            #replace the old string in the list with the first part
            text_to_string[start_row]=first_part

            #insert the second part of the string as a new string right after the first part
            text_to_string.insert(start_row+1,second_part)

        #deal with the text when it is not a newline insertion
        else:

            #get the string where the insertion happened
            change_string=text_to_string[start_row]

            #insert the new string into certain position of the old string according to the column and replace the
            #old one in the list
            text_to_string[start_row]=insert(change_string,type_in,start_column)

    #deal with remove text action
    elif (action=='removeText'):

        #load the remove text
        type_in=change['text']

        #deal with the text when it is a line remove
        if (type_in=='\n'):

            #get the two string between them the remove line action happened
            change_string_1=text_to_string[start_row]
            change_string_2=text_to_string[end_row]

            #combine them into one string to remove the line and replace it with the first old string in the list
            text_to_string[start_row]=change_string_1+change_string_2

            #remove the second old string in the list
            text_to_string.pop(end_row)

        #deal with the text when it is a string remove
        else:

            #get the string where the deletion happened
            change_string=text_to_string[start_row]

            #remove the substring from the string according to the column position
            text_to_string[start_row]=change_string[:start_column]+change_string[end_column:]

    #deal with insertline action
    elif (action=='insertLines'):
        # load the list of the insertion string
        type_in=change['lines']

        #use counter as the increament insertion position
        counter=start_row

        #insert the string in the type_in information
        for a in type_in:
            text_to_string.insert(counter,a)
            counter+=1

    #deal with removeline action
    elif (action=='removeLines'):

        #a counter to caculate how many rows need to be remove
        counter=start_row

        #remove the string in between the range of start row and end row
        while(counter<end_row):
            text_to_string.pop(start_row)
            counter+=1

    #recombine the string with the new line symbol
    new_client_text='\n'.join(text_to_string)

    #return the json form of the client text
    return json.dumps(new_client_text)


# user class definition
class User(object):
    _cursor = None

    # user id start num
    next_user = 0

    #user construction
    def __init__(self, cursor=None,name=None):
        #user's id construction
        self.id = User.next_user

        #increment the id for the next user
        User.next_user += 1

        #user's name construction
        self.username=name or "user" + str(User.next_user)

        #user's cursor construction
        self.cursor = cursor or Cursor(0, 0)

        #a line to seperate the two connection user info
        print '--'

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        self._cursor = value
        [x.broadcast_to(source=self) for x in users if x is not self]




class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the chatroom page"""
    def get(self):

        self.render('index.html')


# ChatConnection class
class ChatConnection(sockjs.tornado.SockJSConnection):
    """Chat connection implementation"""
    # Class level variable

    #participants list
    participants = []

    #users list
    users = []

    #the change from the users based on the current client_text
    client_text_delta=[]

    #the set to check if there are more than one user typing during the period
    typing_user_num_check=set()

    client_text=json.dumps("\n")

    #remember all the cursors latest action
    cursor_position=[]

    #a tuple list recording the user's id and the user typing_in message's row
    user_typing_row=[]

    #a list of the change because of the time lag between user and server communication after the client text
    # update command is sent to user
    collison_fix_delta=[]
    

    def on_open(self, info):

        #get the username from the user
        cookie_name=str(info.cookies).replace("Set-Cookie: username=","",1)
        cookie_name=urllib.unquote(cookie_name).decode('utf8')

        # Add client to the clients list
        self.participants.append(self)

        # Create user and add it to the user list
        self.users.append(User(name=cookie_name))

        #current user's index in the list
        index=len(users)-1

        # create new user's cursor on other user's screen
        constructor=json.dumps({
                'act': 'create_cursor',
                'name': self.users[index].username,
                'user_id': self.users[index].id,
                'row': self.users[index].cursor.row,
                'column': self.users[index].cursor.column
            })

        # broadcast the new user's cursor to other users
        self.broadcast(
            (x for x in self.participants if x != self),
            constructor,
        )

        # broadcast client text to the new user
        self.broadcast(
            (x for x in self.participants if x == self),
            json.dumps({
                               'act': 'startup',
                               'info': ChatConnection.client_text
                           })
        )

        # setup the modification of the client text to the new user
        for a in self.client_text_delta:

            self.broadcast((x for x in self.participants if x == self), a)

        # update all users' lastest cursor position to the new user
        for a in self.cursor_position:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # add the new user's cursor to the cursor list
        self.cursor_position.append((self.users[index].id,constructor))



    def on_message(self, message):

        #deal with the new input from the user
        if ("action" in message):

            #the user to the set of the typing user num list
            self.typing_user_num_check.add(self);

            #broadcast the typing info to the other user
            self.broadcast((x for x in self.participants if x != self), message)

            #record the change after the client test is updated
            self.client_text_delta.append(message)

            #record the change because of the time lag between user and server communication after the client text
            # updatecommand is sent to user
            self.collison_fix_delta.append(message)

            #update the client text
            ChatConnection.client_text=delta_change_apply(ChatConnection.client_text,message)

            #cleat the list recording the change after last time client text updated
            self.client_text_delta.pop()

            # load the message to change it from a json string back to an object which is in the form of
            # {"action":"insertText","range":{"start":{"row":0,"column":0},"end":{"row":0,"column":1}},"text":"a"}
            delta=json.loads(message)

            #load the range aspect of the delta object
            range=delta['range']

            #load the start aspect of the range object
            start=range['start']

            #load the end aspect of the range object
            end=range['end']

            #load the row aspect of the start object
            start_row=start['row']

            #load the row apsect of the end object
            end_row=end['row']

            #check if the start row is the same as the end row in a single import to reduce the information
            # recorded in the user typing row list. If there the start row and the end row of user typing is the same
            # record one of them as the tuple object with the user id and the row num. If they are not the same, then
            #record both of them as tuple objects with user id and the row nums.
            if(start_row == end_row):
                self.user_typing_row.append(
                    (self.users[self.participants.index(self)].id,
                    start_row)
                )
            else:
                 self.user_typing_row.append(
                    (self.users[self.participants.index(self)].id,
                    start_row)
                )
                 self.user_typing_row.append(
                    (self.users[self.participants.index(self)].id,
                    end_row)
                )


        #deal with the new mouse selection action of the user and record it to the stack
        elif("start" in message):

            #load the message to change it from a json string back to an object whcih is in the form of
            # {"start":{"row":0,"column":0},"end":{"row":1,"column":1}}
            cursor=json.loads(message)

            #load the start aspect of the range object
            start=cursor['start']

            #load the end aspect of the range object
            end=cursor['end']

            #the change selection command formed
            constructor=json.dumps({
                    'act': 'change_selection',
                    'name': self.users[self.participants.index(self)].username,
                    'user_id': self.users[self.participants.index(self)].id,
                    'start_row': start['row'],
                    'start_column': start['column'],
                    'end_row': end['row'],
                    'end_column': end['column'],
                })

            #broadcast the selection change to all the other users
            self.broadcast(
                (x for x in self.participants if x != self),
                constructor,
            )

            #update this change to the cursor position
            for x in self.cursor_position:

                #check if there is already an action in the list for the current users' mouse action
                if (x[0]==self.users[self.participants.index(self)].id):

                    #if is remove it
                    self.cursor_position.remove(x)

            #append the new one to the cursor position list
            self.cursor_position.append(
                (self.users[self.participants.index(self)].id,
                constructor)
            )

        #deal with the new mouse move action of the user and record it to the stack
        else:

            #load the message to change it from a json string back to an object whcih is in the form of
            # {"row":0,"column":0}
            cursor=json.loads(message)

            #form the command of cursor moving
            constructor=json.dumps({
                    'act': 'move_cursor',
                    'name': self.users[self.participants.index(self)].username,
                    'user_id': self.users[self.participants.index(self)].id,
                    'row': cursor['row'],
                    'column': cursor['column'],
                })

            #broadcast the cursor move action to all the other users
            self.broadcast(
                (x for x in self.participants if x != self),
                constructor,
            )

             #update this change to the cursor position
            for x in self.cursor_position:

                #check if there is already an action in the list for the current users' mouse action
                if (x[0]==self.users[self.participants.index(self)].id):

                     #if is remove it
                    self.cursor_position.remove(x)

            #append the new one to the cursor position list
            self.cursor_position.append(
                (self.users[self.participants.index(self)].id,
                constructor)
            )

    #remove the user from the user list when disconnect and remove it from the cursor list
    def on_close(self):

        #form the command to remove the disconnect user's cursor from other user's screen
        constructor=json.dumps({
                'act': 'remove_cursor',
                'user_id': self.users[self.participants.index(self)].id,
            })

        #broadcast the remove cursor action to all the other users
        self.broadcast(
            (x for x in self.participants if x != self),
            constructor,
        )

        #delete the user's cursor from the cursor position list
        for x in self.cursor_position:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursor_position.remove(x)

        #remove the user from the users' list
        self.users.pop(self.participants.index(self))

        # Remove client from the clients list
        self.participants.remove(self)

#period call to get update the client text
def poll(c):

    #the flag if the file need to be reset
    file_reset=False

     #check if there are more than one user and if during the period there are more than one user editing
     # and whether there are more than one user editing the same line
    if (len(c._connection.participants)>1and len(c._connection.typing_user_num_check)>1):
        for index,first in enumerate(c._connection.user_typing_row):
            for second in c._connection.user_typing_row[(index+1):]:
                if first[0]!=second[0] and first[1]==second[1]:
                    #if meet the three conditions set the file reset flag to be true
                    file_reset=True
                    break
            # when the file reset flag is true break the outside loop
            if(file_reset):
                break

    #clear the list which remember the change before the update client text fired
    # # but the change isn't applied to user0 yet
    del c._connection.collison_fix_delta[:]

    # if the check find the situation meet the three conditions then reset the users' text
    if(file_reset):
        #broadcast the latext client text to all users
        c.broadcast(c._connection.participants,
                json.dumps({
                    'act': 'correction',
                    'info': c._connection.client_text
                })
        )
        for y in c._connection.collison_fix_delta:
             c.broadcast(c._connection.participants,y)
        file_reset=False

    #clear the list which remember the change before the update client text fired
    # # but the change isn't applied to user0 yet
    del c._connection.collison_fix_delta[:]


if __name__ == "__main__":

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    # 1. Create chat router
    ChatRouter = sockjs.tornado.SockJSRouter(ChatConnection, '/chat')

    # 2. Create Tornado application and set the static path
    # you need to modify the path to your own for the project to work
    app = tornado.web.Application(
            [(r"/", IndexHandler)] + ChatRouter.urls,
            static_path="/home/chennan47/collaboredit/static",
    )

    # 3. Make Tornado app listen on port 8080
    app.listen(8080)

    # set up the main loop
    main_loop=tornado.ioloop.IOLoop.instance()

    #period call setup
    pinger = tornado.ioloop.PeriodicCallback(
        lambda: poll(ChatRouter),
        1000,
        io_loop=main_loop,
    )

    #start the period call
    pinger.start()

    # 4. Start IOLoop
    main_loop.start()
