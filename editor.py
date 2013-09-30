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

Cursor = namedtuple('Cursor', ('row', 'column'))

users = []

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

    client_text=""

    #remember all the created cursor, if a user disconnect it will be remove from this list
    cursor_create=[]

    #remember all the cursors latest action
    cursor_position=[]

    #a tuple list recording the user's id and the user typing_in message's row
    user_typing_row=[]

    #a list of the change because of the time lag between user and server communication after the client text
    # updatecommand is sent to user
    collison_fix_delta=[]

    #the flag if the file need to be reset
    file_reset=False


    def on_open(self, info):

        # Add client to the clients list
        self.participants.append(self)

        # Create user and add it to the user list
        self.users.append(User())

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

        # setup all users' cursor to the new user
        for a in self.cursor_create:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # update all users' lastest cursor position to the new user
        for a in self.cursor_position:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # add the new user's cursor to the cursor list
        self.cursor_create.append((self.users[index].id,constructor))



    def on_message(self, message):

        #update the client text and check if need to reset other user's screen
        if("user_0_client_text" in message):

            #remove the pattern from the client text
            m=message.replace("user_0_client_text","")

            #update the client text if necessary
            if(ChatConnection.client_text!=m):
                ChatConnection.client_text=m

            #check if there are more than one user and if during the period there are more than one user editing
            # and whether there are more than one user editing the same line
            if (len(self.participants)>1and len(self.typing_user_num_check)>1):
                for index,first in enumerate(self.user_typing_row):
                    for second in self.user_typing_row[(index+1):]:
                            if first[0]!=second[0] and first[1]==second[1]:
                                #if meet the three conditions set the file reset flag to be true
                                ChatConnection.file_reset=True
                                break
                    # when the file reset flag is true break the outside loop
                    if(ChatConnection.file_reset):
                        break

            # if the check find the situation meet the three conditions then reset the users' text
            if(ChatConnection.file_reset):

                #broadcast the latext client text to all users
                self.broadcast((x for x in self.participants if x != self),
                           json.dumps({
                               'act': 'correction',
                               'info': ChatConnection.client_text
                           })
                )

                #broadcast the delta after the client text is updated to the users
                for a in self.collison_fix_delta:

                    self.broadcast((x for x in self.participants if x == self), a)
                ChatConnection.file_reset=False

            #clear the user typing row list
            del self.user_typing_row[:]

            #clear the number of typing user list
            self.typing_user_num_check.clear()

            #clear the delta after the client text list
            del self.collison_fix_delta[:]

        #deal with the new input from the user
        elif ("action" in message):

            #the user to the set of the typing user num list
            self.typing_user_num_check.add(self);

            #broadcast the typing info to the other user
            self.broadcast((x for x in self.participants if x != self), message)

            #record the change after the client test is updated
            self.client_text_delta.append(message)

            #record the change because of the time lag between user and server communication after the client text
            # updatecommand is sent to user
            self.collison_fix_delta.append(message)

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

        #delete the user's cursor from the created cursor list
        for x in self.cursor_create:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursor_create.remove(x)

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

    #clear the list which remember the change before the update client text fired
    # # but the change isn't applied to user0 yet
    del c._connection.collison_fix_delta[:]

    # get new client text from user 0
    c.broadcast(
        (x for x in c._connection.participants if x== c._connection.participants[0] ),
        json.dumps({'act':'getValue',}),
    )

    #cleat the list recording the change after last time client text updated
    del c._connection.client_text_delta[:]


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
