# -*- coding: utf-8 -*-
"""
    Simple sockjs-tornado coedit application.
    By default will listen on port 8080.
"""

import tornado.ioloop
import tornado.web
import json
import sockjs.tornado
from collections import namedtuple
import urllib

Cursor = namedtuple('Cursor', ('row', 'column'))

users = []


def insert(original, new, pos):
    """
        function to insert a string into another string in certain position
        :param original: the string to be modified
        :param new: the string to insert
        :param pos: the index of the string character to insert the new string
    """
    return original[:pos] + new + original[pos:]


def delta_change_apply(client_text, delta):
    """
        function to apply the change to the client text
        :param client_text: the client text to be modified in json string
        :param delta: object{"action":"","range":"","text" or "lines":""}
    """

    #JSON.parse
    change = json.loads(delta)

    action = change['action']
    input_range = change['range']

    start = input_range['start']
    start_row = int(start['row'])
    start_column = int(start['column'])

    end = input_range['end']
    end_row = int(end['row'])
    end_column = int(end['column'])

    # break the client text into lines
    lines = json.JSONDecoder(strict=False).decode(client_text).split('\n')

    if action == 'insertText':

        #load the input text
        input_text = change['text']

        #deal with a new line insertion
        if input_text == '\n':

            #get the row where the insertion newline happened
            change_string = lines[start_row]

            #replace the old string in the list with string
            # before the new line insertion
            lines[start_row] = change_string[:start_column]

            #insert the rest of the string as a new string
            # right after the first part
            lines.insert(start_row+1, change_string[start_column:])

        #deal with a string insertion
        else:

            #get the string where the insertion happened
            change_string = lines[start_row]

            #insert the new string into certain position of the old string
            #according to the column, replace the old one in the list
            lines[start_row] = insert(change_string,input_text,start_column)

    elif action == 'removeText':

        #load the remove text
        input_text = change['text']

        #deal with one line remove
        if input_text == '\n':

            #combine two lines into one line,
            #replace it with the first old line in the list
            lines[start_row] = lines[start_row]+lines[end_row]

            #remove the second old line in the list
            lines.pop(end_row)

        #deal with a string remove
        else:

            #get the string where the deletion happened
            change_string = lines[start_row]

            #remove the substring from the string
            # according to the column position
            lines[start_row] \
                = change_string[:start_column] + change_string[end_column:]

    elif action == 'insertLines':

        # load the list of the insertion lines
        input_lines = change['lines']

        #insert the list of lines after the start tow
        lines = lines[:start_row] + input_lines + lines[start_row:]

    elif action == 'removeLines':

        #remove the lines between the range of start row and end row
        lines = lines[:start_row] + lines[end_row:]

    #return the updated client text
    return json.dumps('\n'.join(lines))


# user class definition
class User(object):

    _cursor = None

    # user id initial number
    next_user = 0

    def __init__(self, cursor=None, name=None):
        """
            the constructor of the user class
            :param cursor: user's cursor position, default set to be (0,0)
            :param name: username, default set to be "user"+user id
        """

        self.id = User.next_user
        User.next_user += 1

        self.username = name or "user" + str(User.next_user)

        self.cursor = cursor or Cursor(0, 0)

    @property
    def cursor(self):
        """cursor getter function"""
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        """cursor setter function"""
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
    client_text_delta = []

    #the set to check if there are more than one user typing during the period
    typing_user_num_check = set()

    #the default start screen text of the user
    client_text = json.dumps("\n")

    #remember all the cursors latest action
    cursor_position = []

    #a tuple list recording the user's id and the user typing_in message's row
    user_typing_row = []

    #a list of the change because of the time lag
    # between user and server communication after the client text
    # update command is sent to user
    collison_fix_delta = []

    def on_open(self, info):
        """the new user connection setting"""

        #get the username from the user's cookie
        cookie_name\
            = urllib.unquote(str(info.cookies)
                    .replace("Set-Cookie: username=", "", 1)).decode('utf8')

        # Add client to the clients list
        self.participants.append(self)

        # Create user and add it to the user list
        self.users.append(User(name=cookie_name))

        #index of the user in the user list
        index = len(users)-1

        # create new user's cursor on other user's screen
        constructor = json.dumps({
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

        # update all users' latest cursor position to the new user
        for a in self.cursor_position:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # add the new user's cursor to the cursor list
        self.cursor_position.append((self.users[index].id, constructor))

    def on_message(self, message):
        """
            server action when received information from the user
            :param message: the json string received from the user
        """

        #deal with the new input from the user
        if "action" in message:

            #the user to the set of the typing user num list
            self.typing_user_num_check.add(self)

            #broadcast the typing info to the other user
            self.broadcast((x for x in self.participants if x != self), message)

            #record the change after the client test is updated
            self.client_text_delta.append(message)

            #record the change because of the time lag
            # between user and server communication after the client text
            # update command is sent to user
            self.collison_fix_delta.append(message)

            #update the client text
            ChatConnection.client_text\
                = delta_change_apply(ChatConnection.client_text, message)

            #cleat the list recording the change after client text updated
            self.client_text_delta.pop()

            #JSON.parse
            delta = json.loads(message)

            input_range = delta['range']

            start = input_range['start']
            start_row = start['row']

            end = input_range['end']
            end_row = end['row']

            #record the user id and the row they are editing
            if start_row == end_row:
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

        #deal with the new mouse selection action of the user
        elif "start" in message:

            #JSON.parse
            cursor = json.loads(message)

            start = cursor['start']
            end = cursor['end']

            #the change selection command formed
            constructor = json.dumps({
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

                #check if user's cursor position is already in the list
                if x[0] == self.users[self.participants.index(self)].id:

                    self.cursor_position.remove(x)

            #append the new one to the cursor position list
            self.cursor_position.append(
                (self.users[self.participants.index(self)].id,
                 constructor)
            )

        #deal with the mouse move action of the user
        else:

            #JSON.parse
            cursor = json.loads(message)

            #form the command of cursor moving
            constructor = json.dumps({
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

                #check if user's cursor position is already in the list
                if x[0] == self.users[self.participants.index(self)].id:

                    self.cursor_position.remove(x)

            #append the new one to the cursor position list
            self.cursor_position.append(
                (self.users[self.participants.index(self)].id,
                 constructor)
            )

    def on_close(self):
        """disconnect user and remove all his information"""

        #form the command to remove user's cursor from other user's screen
        constructor = json.dumps({
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

                if x[0] == self.users[self.participants.index(self)].id:

                    self.cursor_position.remove(x)

        #remove the user from the users' list and the client list
        self.users.pop(self.participants.index(self))
        self.participants.remove(self)


def poll(c):
    """period call function to check if there is a collison"""

    #the flag if the file need to be reset
    file_reset = False

     #check if there are more than one user connected
     #check if during the period there are more than one user editing
     # and whether there are more than one user editing the same line
    if len(c._connection.participants) > 1\
            and len(c._connection.typing_user_num_check) > 1:

        for index, first in enumerate(c._connection.user_typing_row):
            for second in c._connection.user_typing_row[(index+1):]:

                if first[0] != second[0] and first[1] == second[1]:
                    file_reset = True
                    break

            # when the file reset flag is true break the outside loop
            if file_reset:
                break

    #clear the period typing user check list
    c._connection.typing_user_num_check.clear()

    #clear the list which remember the change before the update client text
    #fired but the change hasn't been applied yet
    del c._connection.collison_fix_delta[:]

    # reset user's text when there is a collison
    if file_reset:

        #broadcast the latest client text to all users
        c.broadcast(c._connection.participants,
                    json.dumps({
                        'act': 'correction',
                        'info': c._connection.client_text
                    })
                    )

        for y in c._connection.collison_fix_delta:
            c.broadcast(c._connection.participants, y)

        file_reset = False

    #clear the list which remember the change before the update client text
    #fired but the change hasn't been applied yet
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
        static_path="static",
    )

    # 3. Make Tornado app listen on port 8080
    app.listen(8080)

    # set up the main loop
    main_loop = tornado.ioloop.IOLoop.instance()

    #period call setup
    ping = tornado.ioloop.PeriodicCallback(
        lambda: poll(ChatRouter),
        1000,
        io_loop=main_loop,
    )

    #start the period call
    ping.start()

    # 4. Start IOLoop
    main_loop.start()
