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


        self.robots_map = {}

        #DO NOT TOUCH THE FOLLOWING INSTRUCTIONS
        self.network = Network(server_ip=server_ip)
        self.agent_id = self.network.id
        self.running = True
        self.network.send({"header": GET_DATA})
        self.msg = {}
        env_conf = self.network.receive()
        self.nb_agent_expected = 0
        self.nb_agent_connected = 0
        self.x, self.y = env_conf["x"], env_conf["y"]   #initial agent position
        self.w, self.h = env_conf["w"], env_conf["h"]   #environment dimensions
        cell_val = env_conf["cell_val"] #value of the cell the agent is located in
        print(cell_val)
        Thread(target=self.msg_cb, daemon=True).start()
        print("hello")
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
                self.nb_agent_expected = msg["nb_agents"]
                
            elif msg["header"] == GET_NB_CONNECTED_AGENTS:
                self.nb_agent_connected = msg["nb_connected_agents"]
                
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
                    print(f"Agent {self.agent_id} cle trouvee!")
                    self.key_map += {"owner":msg["owner"], "position" : msg["position"]}
                elif msg["Msg type"] == BOX_DISCOVERED:  # Box discovered
                    print(f"Agent {self.agent_id} boite trouvee!")
                    self.box_map += {"owner":msg["owner"], "position" : msg["position"]}

                elif msg["Msg type"] == POSITION:
                    self.robots_map[msg["owner"]] = msg["position"]
                    x,y = msg["position"]
                    self.known_map[int(x),int(y)] = 1.0
                    
            

    def wait_for_connected_agent(self):
        self.network.send({"header": GET_NB_AGENTS})
        check_conn_agent = True
        while check_conn_agent:
            if self.nb_agent_expected == self.nb_agent_connected:
                print("les deux connectees!")
                check_conn_agent = False

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

        if not heading == 0:
            print("move success")

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

            sleep(0.1) # timeout to be sure the callback has been done

            if self.cell_val == 1: # on a key or a chest
                cell_owner,obj_type = self.get_item_owner_type() # request object type and owner
                
                if not cell_owner == self.agent_id: # object not for this robot
                    self.broadcast_obj_pos(cell_owner,obj_type)
                else:
                    if obj_type == KEY_TYPE:
                        self.key_found = True
                    else:
                        self.box_found = True

                
                print("GOT OBJECT")

    def compute_gradient(self, points):
        gradients = []
        for i in range(len(points) - 1):
            x1, y1, v1 = points[i]
            x2, y2, v2 = points[i + 1]
            dx = x2 - x1
            dy = y2 - y1
            if dx != 0:
                grad_x = (v2 - v1) / dx
            else:
                grad_x = 0
            if dy != 0:
                grad_y = (v2 - v1) / dy
            else:
                grad_y = 0
            gradients.append((grad_x, grad_y))
        # Average gradients
        grad_x_avg = np.mean([g[0] for g in gradients])
        grad_y_avg = np.mean([g[1] for g in gradients])
        return grad_x_avg, grad_y_avg

    def do_descent(self, obj_type):
        self.descent_pos.append((self.x, self.y,self.cell_val))
        if len(self.descent_pos) > 1:
            grad_x, grad_y = self.compute_gradient(self.descent_pos)
            if grad_x == 0 and grad_y == 0: # la direction est orthogonale au gradient
                heading = np.tan(self.last_descent_move[0:1]) + np.radians(90)
                x,y = float(np.round(np.cos(heading))), float(np.round(np.sin(heading)))
            else:
                heading = np.arctan2(grad_y, grad_x)
                x,y = round(np.cos(heading)), round(np.sin(heading))
                self.last_descent_move = x,y
        else:
            if x + self.x < 0 or x + self.x >= self.w : # out of bounds
                x = 0
            else:
                x = randint(-1,1)
            
            if y + self.y < 0 or y + self.y >= self.h:
                y = 0
            else:
                y = randint(-1,1)

        print("Descent", "Cle" if obj_type== KEY_TYPE else "Box")
        

        if self.cell_val == 1: # on a key or a chest
            self.in_descent = False # stop descent
            self.descent_cooldown = 20
            self.descent_pos = []
            x,y = 0,0 # do not move
        return (x,y)
    
    def move_to(self, obj_type):
        """
        Move to an object that has been sent via broadcast ( coordinates are known )
        Returns """
        print("move to ", obj_type)
        if obj_type == KEY_TYPE:
            obj_map = self.key_map
        else:
            obj_map = self.box_map

        if len(obj_map) > 1:
            obj_pos = obj_map[0]["position"]
        else:
            return (0,0)
        
        offset_x,offset_y = obj_pos[0] - self.x, obj_pos[1] - self.y

        heading = np.arctan2(offset_y, offset_x) # normalize vector to 1 for movement
        x,y = round(np.cos(heading)), round(np.sin(heading))

        return (x,y)

    def explore(self):
        print("explore")
        x,y = randint(-1,1),randint(-1,1)
        if not self.cell_val == 0 and self.descent_cooldown <= 0:
            self.in_descent = True
            self.descent_pos.append((self.x, self.y,self.cell_val))
        else:
            self.descent_cooldown -= 1
        
        return (x,y)


    def compute_move(self):
        """
        Computes the next move for the agent based on its current state.
        :return: Coordinates (x, y) for the next move.
        """
        if self.key_found:
            if self.box_found:
                return 0, 0
            if self.in_descent:
                return self.do_descent(BOX_TYPE)
            else:
                if self.agent_id in [box["owner"] for box in self.box_map]: # our box has been broadcasted
                    return self.move_to(BOX_TYPE)
                else:
                    return self.explore()
        else:
            if self.in_descent:
                return self.do_descent(KEY_TYPE)
            else:
                if self.agent_id in [key["owner"] for key in self.key_map]: # our box has been broadcasted
                    return self.move_to(KEY_TYPE)
                else:
                    return self.explore()

        # Default to staying in the current position if no move is computed
        return 0, 0



if __name__ == "__main__":
    from random import randint
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--server_ip", help="Ip address of the server", type=str, default="localhost")
    args = parser.parse_args()

    agent = Agent(args.server_ip)

    agent.main_loop()  # Start autonomous agent behavior
    
    try:    #Manual control test0
        while True:
            cmds = {"header": int(input("0 <-> Broadcast msg\n1 <-> Get data\n2 <-> Move\n3 <-> Get nb connected agents\n4 <-> Get nb agents\n5 <-> Get item owner\n"))}
            if cmds["header"] == BROADCAST_MSG:
                cmds["Msg type"] = int(input("1 <-> Key discovered\n2 <-> Box discovered\n3 <-> Completed\n"))
                cmds["position"] = (agent.x, agent.y)
                cmds["owner"] = randint(0,3) # TODO: specify the owner of the item
            elif cmds["header"] == MOVE:
                cmds["direction"] = int(input("0 <-> Stand\n1 <-> Left\n2 <-> Right\n3 <-> Up\n4 <-> Down\n5 <-> UL\n6 <-> UR\n7 <-> DL\n8 <-> DR\n"))
            agent.network.send(cmds)
    except KeyboardInterrupt:
        pass
