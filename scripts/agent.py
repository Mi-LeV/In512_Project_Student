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
        


        

    def msg_cb(self): 
        """ Method used to handle incoming messages """
        while self.running:
            msg = self.network.receive()
            self.msg = msg
            
            # Handling different message types
            if msg["header"] == MOVE:
                self.x, self.y = msg["x"], msg["y"]
                print(f"Agent bouge a la position: ({self.x}, {self.y})")
                
            elif msg["header"] == GET_NB_AGENTS:
                self.nb_agent_expected = msg["nb_agents"]
                
            elif msg["header"] == GET_NB_CONNECTED_AGENTS:
                self.nb_agent_connected = msg["nb_connected_agents"]
                
            elif msg["header"] == GET_DATA:
                print(f"Valeur de cellule recu: {msg['cell_val']}")
                
            # Handle item discovery
            if msg["header"] == BROADCAST_MSG:
                if msg["Msg type"] == 1:  # Key discovered
                    print(f"Agent {self.agent_id} cle trouvee!")
                    self.key_found = True
                elif msg["Msg type"] == 2:  # Box discovered
                    print(f"Agent {self.agent_id} boite trouvee!")
                    self.box_found = True
            

    def wait_for_connected_agent(self):
        self.network.send({"header": GET_NB_AGENTS})
        check_conn_agent = True
        while check_conn_agent:
            if self.nb_agent_expected == self.nb_agent_connected:
                print("les deux connectees!")
                check_conn_agent = False

                  

    def navigation(self):
        """ Manual control for agent movement and broadcasting """
        while True:
            cmds = {"header": int(input("Choose an action:\n0 <-> Broadcast msg\n1 <-> Get data\n2 <-> Move\n3 <-> Get nb connected agents\n4 <-> Get nb agents\n5 <-> Get item owner\n"))}
            
            # Broadcast message (Key, Box, or Completed)
            if cmds["header"] == BROADCAST_MSG:
                cmds["Msg type"] = int(input("1 <-> Key discovered\n2 <-> Box discovered\n3 <-> Completed\n"))
                cmds["position"] = (self.x, self.y)
                cmds["owner"] = randint(0, 3)  # Specify the owner of the item
            
            # Movement
            elif cmds["header"] == MOVE:
                 cmds["direction"] = int(input("0 <-> Stand\n1 <-> Left\n2 <-> Right\n3 <-> Up\n4 <-> Down\n5 <-> UL\n6 <-> UR\n7 <-> DL\n8 <-> DR\n"))
                 self.network.send(cmds)


            # Get data
            elif cmds["header"] == 1:
                self.network.send({"header": GET_DATA})

            # Send message to the network
            self.network.send(cmds)

     



    def agent_behavior(self):
        """ Autonomous agent behavior to search for the key and the box """
        while self.running:
            if not self.key_found:
                print(f"Agent {self.agent_id} searching for the key...")
                self.search_for_key()
        
            # Si la clé est trouvée, commencer la recherche de la boîte
            if self.key_found and not self.box_found:
                print(f"Agent {self.agent_id} searching for the box...")
                self.search_for_box()
        
            # Si la boîte est trouvée, mission accomplie mais continuer à chercher d'autres éléments
            if self.key_found and self.box_found:
                print(f"Agent {self.agent_id} has completed its mission!")
                # Supposons que l'agent continue de chercher d'autres objets ou attend
                break
        
            sleep(1)  # Sleep to simulate decision-making time


     

    def search_for_key(self):
        """ Search for the key by moving around the environment """
        directions = [1, 2, 3, 4, 5, 6, 7, 8]  # Possible move directions (left, right, up, down, diagonals)
        direction = randint(0, 7)  # Randomly choose a direction to move
        self.move_agent(direction)

        # Simulate the search for the key: if it's found, mark key_found as True
        if randint(0, 10) > 8:  # 20% chance to "find" the key (this is just a placeholder logic)
            self.key_found = True
            print(f"Key found by Agent {self.agent_id} at position ({self.x}, {self.y})")

    
        # Simulate the search for the key: if it's found, mark key_found as True
            if randint(0, 10) > 8:  # 20% chance to "find" the key (this is just a placeholder logic)
                self.key_found = True
                print(f"Key found by Agent {self.agent_id} at position ({self.x}, {self.y})")




    # nouvelle fonction cree par rayan 3
    def search_for_box(self):
        """ Search for the box by moving around the environment """
        directions = [1, 2, 3, 4, 5, 6, 7, 8]  # Possible move directions (left, right, up, down, diagonals)
        direction = randint(0, 7)  # Randomly choose a direction to move
        self.move_agent(direction)

        # Simulate the search for the box: if it's found, mark box_found as True
        if randint(0, 10) > 8:  # 20% chance to "find" the box
            self.box_found = True
            print(f"Box found by Agent {self.agent_id} at position ({self.x}, {self.y})")




    # nouvelle fonction cree par rayan 4
    def move_agent(self, direction):
        """ Send move command to the agent based on the chosen direction """
        cmds = {"header": MOVE, "direction": direction}
        self.network.send(cmds)




if __name__ == "__main__":
    from random import randint
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--server_ip", help="Ip address of the server", type=str, default="localhost")
    args = parser.parse_args()

    agent = Agent(args.server_ip)

    agent.agent_behavior()  # Start autonomous agent behavior
    
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
# it is always the same location of the agent first location