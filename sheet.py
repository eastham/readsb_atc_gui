

#!/usr/bin/python3

import pygsheets

class Sheet:
    def __init__(self, name):
        gc = pygsheets.authorize(local=True)
        sh = gc.open(name)
        self.wks = sh.sheet1

    def write(self, matrix):
        print("write to sheet " + str(matrix))
        self.wks.update_values('A2', matrix)
