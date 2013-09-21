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

    next_user = 0

    def __init__(self, cursor=None,name=None):

        self.id = User.next_user
        User.next_user += 1
        self.username=name or "user" + str(User.next_user)
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
    participants = []
    users = []
    board=[]
    checks=set()
    clientText=""
    cursorCreate=[]
    cursorPosition=[]
    messagecheck=[]
    comtimefix=[]
    change=False


    def on_open(self, info):

        # Add client to the clients list
        self.participants.append(self)
        # Create user and add it to the user list
        self.users.append(User())
        index=len(users)-1
        # create new user's cursor on other user's screen
        constructor=json.dumps({
                'act': 'create_cursor',
                'name': self.users[index].username,
                'user_id': self.users[index].id,
                'row': self.users[index].cursor.row,
                'column': self.users[index].cursor.column
            })

        # broad the new user's cursor to other user'
        self.broadcast(
            (x for x in self.participants if x != self),
            constructor,
        )

        # setup clienttext to the new user
        self.broadcast(
            (x for x in self.participants if x == self),
            json.dumps({
                               'act': 'startup',
                               'info': ChatConnection.clientText
                           })
        )

        # setup the modification of the client text to the new user
        for a in self.board:

            self.broadcast((x for x in self.participants if x == self), a)

        #setup the users' cursor to the new user
        for a in self.cursorCreate:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # update the users' lastest cursor position to the new user
        for a in self.cursorPosition:

            self.broadcast((x for x in self.participants if x == self), a[1])

        # add the new user's cursor to the cursor list
        self.cursorCreate.append((self.users[index].id,constructor))



    def on_message(self, message):

        #update the client text and check if need to reset other user's screen
        if("user_0_client_text" in message):

            #remove the pattern from the client text
            m=message.replace("user_0_client_text","")

            ChatConnection.clientText=m

            #check if there are more than one user and if during the period there are more than two users editing
            # and whether there are more than one user editing the same line
            if (len(self.participants)>1and len(self.checks)>1):
                for index,first in enumerate(self.messagecheck):
                    for second in self.messagecheck[(index+1):]:
                            if first[0]!=second[0] and first[1]==second[1]:
                                ChatConnection.change=True
                                break
                    if(ChatConnection.change):
                        break

            # if the check find the situation meet the condition then reset the users' text
            if(ChatConnection.change):
                self.broadcast((x for x in self.participants if x != self),
                           json.dumps({
                               'act': 'correction',
                               'info': ChatConnection.clientText
                           })
                )
                for a in self.comtimefix:

                    self.broadcast((x for x in self.participants if x == self), a)
                ChatConnection.change=False

            #clear the stack
            del self.messagecheck[:]
            self.checks.clear()
            del self.comtimefix[:]

        #deal with the new input from the user
        elif ("action" in message):

            #apply the change and add certain info to the stack
            self.checks.add(self);
            self.broadcast((x for x in self.participants if x != self), message)
            self.board.append(message)
            self.comtimefix.append(message)

            # record and analysize the message for the message check
            delta=json.loads(message)
            range=delta['range']
            start=range['start']
            end=range['end']
            start_row=start['row']
            end_row=end['row']

            if(start_row == end_row):
                self.messagecheck.append(
                    (self.users[self.participants.index(self)].id,
                    start_row)
                )
            else:
                 self.messagecheck.append(
                    (self.users[self.participants.index(self)].id,
                    start_row)
                )
                 self.messagecheck.append(
                    (self.users[self.participants.index(self)].id,
                    end_row)
                )


        #deal with the new mouse selection action of the user and record it to the stack
        elif("start" in message):
            # print(message);
            cursor=json.loads(message)
            start=cursor['start']
            end=cursor['end']
            constructor=json.dumps({
                    'act': 'change_selection',
                    'user_id': self.users[self.participants.index(self)].id,
                    'start_row': start['row'],
                    'start_column': start['column'],
                    'end_row': end['row'],
                    'end_column': end['column'],
                })
            self.broadcast(
                (x for x in self.participants if x != self),
                constructor,
            )

            for x in self.cursorPosition:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursorPosition.remove(x)

            self.cursorPosition.append(
                (self.users[self.participants.index(self)].id,
                constructor)
            )

        #deal with the new mouse move action of the user and record it to the stack
        else:

            cursor=json.loads(message)
            constructor=json.dumps({
                    'act': 'move_cursor',
                    'user_id': self.users[self.participants.index(self)].id,
                    'row': cursor['row'],
                    'column': cursor['column'],
                })
            self.broadcast(
                (x for x in self.participants if x != self),
                constructor,
            )

            for x in self.cursorPosition:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursorPosition.remove(x)

            self.cursorPosition.append(
                (self.users[self.participants.index(self)].id,
                constructor)
            )

    #remove the user from the user list when disconnect and remove it from the cursor list
    def on_close(self):
        constructor=json.dumps({
                'act': 'remove_cursor',
                'user_id': self.users[self.participants.index(self)].id,
            })
        self.broadcast(
            (x for x in self.participants if x != self),
            constructor,
        )

        for x in self.cursorCreate:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursorCreate.remove(x)

        for x in self.cursorPosition:

                if (x[0]==self.users[self.participants.index(self)].id):

                    self.cursorPosition.remove(x)

        # Remove client from the clients list
        self.users.pop(self.participants.index(self))
        self.participants.remove(self)

#period call to get update the client text
def poll(c):

    del c._connection.comtimefix[:]
    c.broadcast(
        (x for x in c._connection.participants if x== c._connection.participants[0] ),
        json.dumps({'act':'getValue',}),
    )

    del c._connection.board[:]


if __name__ == "__main__":

    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    # 1. Create chat router
    ChatRouter = sockjs.tornado.SockJSRouter(ChatConnection, '/chat')

    # 2. Create Tornado application
    app = tornado.web.Application(
            [(r"/", IndexHandler)] + ChatRouter.urls,
            static_path="/home/chennan47/collaboredit/static",
    )

    # 3. Make Tornado app listen on port 8080
    app.listen(8080)

    main_loop=tornado.ioloop.IOLoop.instance()

    #period call setup
    pinger = tornado.ioloop.PeriodicCallback(
        lambda: poll(ChatRouter),
        1000,
        io_loop=main_loop,
    )

    pinger.start()
    # 4. Start IOLoop
    main_loop.start()
