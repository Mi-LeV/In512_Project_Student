__author__ = "Aybuke Ozturk Suri, Johvany Gustave"
__copyright__ = "Copyright 2023, IN512, IPSA 2024"
__credits__ = ["Aybuke Ozturk Suri", "Johvany Gustave"]
__license__ = "Apache License 2.0"
__version__ = "1.0.0"

from network import Network
from my_constants import *

from threading import Thread
import numpy as np
from time import sleep

#new import
from random import randint


class Agent:
    """ Class that implements the behaviour of each agent based on their perception and communication with other agents """
    def __init__(self, server_ip):
        #TODO: DEINE YOUR ATTRIBUTES HERE

        self.x, self.y = None, None   # Position of the agent
        self.w, self.h = None, None   # Environment dimensions (width, height)
        self.agent_id = None          # ID of the agent
        self.key_found = False        # Whether the agent found the key
        self.box_found = False        # Whether the agent found the box
        self.items_collected = []     # Track the items found

        self.portion_init = False


        self.robots_map = {}

        #DO NOT TOUCH THE FOLLOWING INSTRUCTIONS
        self.network = Network(server_ip=server_ip)
        self.agent_id = self.network.id
        self.running = True
        self.network.send({"header": GET_DATA})
        self.msg = {}
        env_conf = self.network.receive()
        self.nb_agents_expected = 10
        self.nb_agents_connected = 0
        self.x, self.y = env_conf["x"], env_conf["y"]   #initial agent position
        self.w, self.h = env_conf["w"], env_conf["h"]   #environment dimensions

        Thread(target=self.msg_cb, daemon=True).start()
        self.wait_for_connected_agent()

        
        self.cell_val = 0.0
        self.cell_owner = -1
        self.cell_type = -1
        self.known_map = np.zeros((self.w, self.h))
        self.key_map = []
        self.box_map = []

        self.in_descent = False
        self.descent_pos = []
        self.last_descent_move = 1,1
        self.descent_cooldown = 0
        self.explore_finished = False
        self.descent_count = 0
        self.descent_turned_90 = False
        self.descent_go_back_done = False
    
    
    def msg_cb(self): 
        """ Method used to handle incoming messages """
        while self.running:
            msg = self.network.receive()
            self.msg = msg
            
            # Handling different message types
            if msg["header"] == MOVE:
                self.x, self.y = msg["x"], msg["y"]
                self.cell_val = msg["cell_val"]
                self.known_map[self.x,self.y] = 1.0
                print(f"Agent bouge a la position: ({self.x}, {self.y})")
                
            elif msg["header"] == GET_NB_AGENTS:
                self.nb_agents_expected = msg["nb_agents"]
                self.init_map_portion()
                
            elif msg["header"] == GET_NB_CONNECTED_AGENTS:
                self.nb_agents_connected = msg["nb_connected_agents"]
                
            elif msg["header"] == GET_DATA:
                print(f"Valeur de cellule recu: {msg['cell_val']}")
            
            elif msg["header"] == GET_ITEM_OWNER:
                self.cell_owner = msg['owner']
                self.cell_type = msg['type']
                type_obj = "Cle" if msg['type'] == KEY_TYPE else "Box"
                print(f"Valeur de cellule recu: {msg['owner']} , " + type_obj)
            
                
            # Handle item discovery
            if msg["header"] == BROADCAST_MSG:
                if msg["Msg type"] == KEY_DISCOVERED:  # Key discovered

                    self.update_map_portion(msg["position"])
                    self.key_map.append({"owner": msg["owner"], "position": msg["position"]})
                elif msg["Msg type"] == BOX_DISCOVERED:  # Box discovered

                    self.update_map_portion(msg["position"])
                    self.box_map.append({"owner": msg["owner"], "position": msg["position"]})


                elif msg["Msg type"] == POSITION:
                    self.robots_map[msg["owner"]] = msg["position"]
                    self.update_map_portion(msg["position"])

                    
            

    def wait_for_connected_agent(self):
        
        check_conn_agent = True
        while check_conn_agent:
            self.network.send({"header": GET_NB_AGENTS})
            sleep(0.2)

            self.network.send({"header": GET_NB_CONNECTED_AGENTS})
            sleep(0.2)

            print("waiting for other agents...")
            if self.nb_agents_expected == self.nb_agents_connected:
                print("all connected !")
                check_conn_agent = False
            else:
                sleep(1)
                
                

    def move(self,x,y):
        """
        Sends the move command to the server to go to the given offset (x,y)

            Parameters:
                    x (int): x offset
                    b (int): y offset

        """
        command = {"header": 2}


        heading = 0

        if x == -1 and y == 0:
            heading = 1
        elif x == 1 and y == 0:
            heading = 2
        elif x == 0 and y == -1:
            heading = 3
        elif x == 0 and y == 1:
            heading = 4
        elif x == -1 and y == -1:
            heading = 5
        elif x == 1 and y == -1:
            heading = 6
        elif x == -1 and y == 1:
            heading = 7
        elif x == 1 and y == 1:
            heading = 8

        if x + self.x < 0 or x + self.x >= self.w or y + self.y < 0 or y + self.y >= self.h : # out of bounds
            heading = 0
            print("hitting the wall")
            
        command["direction"] = heading
        self.network.send(command)
    


    def broadcast_new_pos(self,x,y):
        """
        Broadcast the new position of the robot (x,y) with the agent ID.

            Parameters:
                    x (int): new x position
                    b (int): new y position

        """
        command = {"header": BROADCAST_MSG}
        command["Msg type"] = POSITION
        command["position"] = (x, y)
        command["owner"] = self.agent_id

        self.network.send(command)

    def get_item_owner_type(self):
        command = {"header": GET_ITEM_OWNER}
        self.network.send(command)

        sleep(0.1) # timeout to be sure the callback has been done

        return (self.cell_owner, self.cell_type)

    def broadcast_obj_pos(self, cell_owner, obj_type):
        command = {"header": BROADCAST_MSG}
        if obj_type == KEY_TYPE:
            command["Msg type"] = KEY_DISCOVERED
        else:
            command["Msg type"] = BOX_DISCOVERED

        command["position"] = (self.x, self.y)
        command["owner"] = cell_owner

        self.network.send(command)

                  
    def main_loop(self):
        while True:
            #x,y = 0,0
            x,y = self.compute_move() # position of next move

            for key, (robot_x, robot_y) in self.robots_map.items():
                if robot_x == self.x and robot_y == self.y:  # if blocked by other bots
                    print("avoiding collision")
                    continue # do not move

            self.move(x,y) # move to new pos
            self.broadcast_new_pos(x,y) # broadcast new pos to others
            
            
            self.update_map_portion((self.x,self.y))

            sleep(0.2) # timeout to be sure the callback has been done

            if self.cell_val == 1: # on a key or a chest
                cell_owner,obj_type = self.get_item_owner_type() # request object type and owner
                
                if not cell_owner == self.agent_id: # object not for this robot
                    self.broadcast_obj_pos(cell_owner,obj_type)
                else:
                    if obj_type == KEY_TYPE:
                        self.key_found = True
                        self.key_map = []
                    elif self.key_found:
                        self.box_found = True
                        self.box_map = []
                    else:
                        self.box_map.append({"owner": self.agent_id, "position": (self.x,self.y)}) # found box before key


                print("GOT OBJECT")

                if self.key_found and self.box_found:
                    print("FINISHED !!!!")
                    return


    def do_descent(self):
        # Append current position and cell value to descent history
        self.descent_pos.append((self.x, self.y, self.cell_val))
        

        if self.descent_pos[-1][2] > self.descent_pos[-2][2]:
            dx,dy = self.last_descent_move # go forward
                
            print("DESCENT: CONTINUE")

        else:
            if not self.descent_go_back_done:
                dx,dy = (-self.last_descent_move[0],-self.last_descent_move[1]) # go back
                self.descent_go_back_done = True
                print("DESCENT: GO BACK")

            else:
                if not self.descent_turned_90:
                    heading = np.arctan2(self.last_descent_move[1], self.last_descent_move[0]) + np.radians(90)
                    dx, dy = int(np.round(np.cos(heading))), int(np.round(np.sin(heading)))
                    self.descent_turned_90 = True
                    self.descent_go_back_done = False
                    print("DESCENT: TURN 90")


                else:
                    dx,dy = (-self.last_descent_move[0],-self.last_descent_move[1]) # go back
                    self.descent_turned_90 = False
                    print("DESCENT: TURN 180")

                    

        # Update position

        print(f"DESCENT: MOVE ({dx}, {dy})")
        self.last_descent_move = (dx,dy)
            

        if self.cell_val == 1: # on a key or a chest
            print("DESCENT : SUCESS !")
            self.descent_count = 0
            self.in_descent = False # stop descent
            self.descent_cooldown = 5
            self.descent_pos = []
            dx,dy = 0,0 # do not move
        else:
            if self.descent_count > 20 : 
                print("DESCENT : FAILED !")
                self.descent_count = 0
                self.in_descent = False # stop descent
                self.descent_cooldown = 5
                self.descent_pos = []
                dx,dy = 0,0 # do not move
            else:
                self.descent_count += 1
        return (dx,dy)
    
    def move_to(self, obj_type):
        """
        Move to an object that has been sent via broadcast ( coordinates are known )
        Returns 
        """

        

        print("MOVE TO : ", obj_type)
        if obj_type == KEY_TYPE:
            obj_map = self.key_map
        else:
            obj_map = self.box_map

        obj_found = False
        if isinstance(obj_map, dict):  # If obj_map is a dictionary, treat it as a list with one element
            obj_map = [obj_map]

        for obj in obj_map:
            print(f"MOVE TO : OBJ LIST {obj}")
            if obj["owner"] == self.agent_id:
                obj_pos = obj["position"]
                obj_found = True
                break

        if not obj_found:
            print(f"MOVE TO : NO OBJ {obj_type} IN LIST")
            return (0,0)

        
        offset_x,offset_y = obj_pos[0] - self.x, obj_pos[1] - self.y

        heading = np.arctan2(offset_y, offset_x) # normalize vector to 1 for movement
        x,y = round(np.cos(heading)), round(np.sin(heading))

        return (x,y)

    def init_map_portion(self):

        if self.portion_init:
            return
        else:
            self.portion_init = True
        


        self.map_portion = np.zeros((self.w, self.h))

        # Ensure region_width is at least 1 to avoid division issues
        region_width = max(1, self.w // self.nb_agents_expected)

        # Compute the start and end columns for the specified region


        start_col = self.agent_id * region_width
        end_col = start_col + region_width

        # Ensure the last agent's region covers the remaining columns
        if self.agent_id == self.nb_agents_expected - 1:
            end_col = self.w

        # Adjust indices to ensure agents only explore their assigned region
        start_col = max(0, start_col)
        end_col = min(self.w, end_col)

        self.map_portion[start_col:end_col,:] = 1



    def update_map_portion(self,obj_pos):
        x,y = obj_pos
        last_map_portion = self.map_portion.copy()  # a virer
        self.map_portion[max(0, x-2):min(self.map_portion.shape[0], x+3),\
                         max(0, y-2):min(self.map_portion.shape[1], y+3)] = 0

        

    def explore(self):

        # compute the nearest unexplored pixel

        nearest_distance = float('inf')
        best_move = None
        x,y = 0,0

        for i in range(self.w):
            for j in range(self.h):
                if self.map_portion[i, j] == 1:
                    distance = np.sqrt((i - self.x)**2 + (j - self.y)**2)
                    if distance < nearest_distance:
                        nearest_distance = distance
                        best_move = (i - self.x, j - self.y)

        if best_move:
            dx, dy = best_move
            print(f"EXPLORE : BEST MOVE ({best_move})")
            x = int(dx / abs(dx)) if dx != 0 else 0
            y = int(dy / abs(dy)) if dy != 0 else 0

        else:
            print("EXPLORE : NO UNEXPLORED PIXELS")
            self.explore_finished = True

        # DESCENT
    
        if self.cell_val != 0 and self.descent_cooldown <= 0: # enter descent
            self.in_descent = True
            self.descent_pos.append((self.x, self.y,self.cell_val))
            self.last_descent_move = (x,y)
            self.descent_go_back_done = False
        else: # update descent cooldown
            self.descent_cooldown -= 1

        
        return (x,y)


    def compute_move(self):
        """
        Computes the next move for the agent based on its current state.
        :return: Coordinates (x, y) for the next move.
        """
        if self.in_descent:
            return self.do_descent()
        else:
            if not self.explore_finished :
                return self.explore()
            else:
                if not self.key_found:
                    return self.move_to(KEY_TYPE)
                else:
                    return self.move_to(BOX_TYPE)




if __name__ == "__main__":
    from random import randint
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--server_ip", help="Ip address of the server", type=str, default="localhost")
    args = parser.parse_args()

    agent = Agent(args.server_ip)

    agent.main_loop()  # Start autonomous agent behavior
    while True:  # keep alive
        pass