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

        self.x, self.y = None, None   # Position of the agent
        self.w, self.h = None, None   # Environment dimensions (width, height)
        self.agent_id = None          # ID of the agent
        self.key_found = False        # Whether the agent found the key
        self.box_found = False        # Whether the agent found the box
        self.items_collected = []     # Track the items found

        self.portion_init = False


        self.robots_map = {}
        self.walked_map = []

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
        self.obstacle_map = np.zeros((self.w, self.h))
        self.key_map = []
        self.box_map = []

        self.in_descent = False
        self.descent_pos = []
        self.last_descent_move = (0,0)
        self.descent_cooldown = 0
        self.explore_finished = False
        self.descent_count = 0
        self.descent_turned_90 = False
        self.descent_go_back_done = False

        self.last_move = (0, 0)
        self.go_back = False

    
    
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
                    if not msg["position"] in self.walked_map:
                        self.walked_map.append(msg["position"])

                    
            

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
        """
        Main loop controlling the robot's behavior.
        Continuously computes moves, updates its position, interacts with objects,
        and communicates with other robots until its task is complete.
        """
        while True:
            # Compute the next move based on the current state
            dx, dy = self.compute_move()

            # Check for potential collisions with other robots
            for key, (robot_x, robot_y) in self.robots_map.items():
                if robot_x == self.x and robot_y == self.y:  # If another robot is blocking
                    print("avoiding collision")
                    continue  # Skip this iteration and avoid moving

            # Move to the newly computed position
            self.move(dx, dy)

            if not (self.x,self.y) in self.walked_map:
                self.walked_map.append((self.x,self.y))

            # Broadcast the new position to other robots
            self.broadcast_new_pos(self.x, self.y)

            # Update the portion of the map based on the new position
            self.update_map_portion((self.x, self.y))

            # Pause briefly to ensure asynchronous callbacks (if any) are processed
            sleep(0.2)

            self.last_move = (dx, dy)

            if self.cell_val == 0.35:
                self.obstacle_map[int(self.x),int(self.y)] = 1
                self.go_back = True
            else:
                self.go_back = False

            # Check the current cell value for special objects
            if self.cell_val == 1:  # Indicates a key or chest is present
                # Get the owner and type of the object in the current cell
                cell_owner, obj_type = self.get_item_owner_type()

                # Handle objects not owned by this robot
                if cell_owner != self.agent_id:
                    self.broadcast_obj_pos(cell_owner, obj_type)
                else:
                    # Handle cases where the robot owns the object
                    if obj_type == KEY_TYPE:
                        self.key_found = True  # Mark key as found
                        self.key_map = []  # Clear the key map
                    elif self.key_found:
                        self.box_found = True  # Mark box as found (after key)
                        self.box_map = []  # Clear the box map
                    else:
                        # If the box is found before the key
                        self.box_map.append({
                            "owner": self.agent_id,
                            "position": (self.x, self.y)
                        })

                print("GOT OBJECT")  # Debug message indicating object interaction

                # Check if both key and box have been found
                if self.key_found and self.box_found and self.explore_finished:
                    print("FINISHED !!!!")  # Task completed
                    print(f"{len(self.walked_map)} EXPLORED IN TOTAL !!!!")
                    return  # Exit the loop



    def do_descent(self):
        """
        Handles the descent process, adjusting the robot's movement based on the current and previous cell values.
        The function uses a heuristic to decide whether to continue, backtrack, turn, or stop descent based on progress.
        """
        # Record the current position and cell value in the descent history
        self.descent_pos.append((self.x, self.y, self.cell_val))

        # Determine movement based on the progress in the descent
        if self.descent_pos[-1][2] > self.descent_pos[-2][2]:
            # Progress has improved (higher cell value), continue forward
            dx, dy = self.last_descent_move
            print("DESCENT: CONTINUE")
        else:
            if not self.descent_go_back_done:
                # No improvement and haven't gone back yet, so backtrack
                dx, dy = (-self.last_descent_move[0], -self.last_descent_move[1])
                self.descent_go_back_done = True
                print("DESCENT: GO BACK")
            else:
                if not self.descent_turned_90:
                    # No improvement after backtracking, turn 90 degrees
                    heading = np.arctan2(self.last_descent_move[1], self.last_descent_move[0]) + np.radians(90)
                    dx, dy = int(np.round(np.cos(heading))), int(np.round(np.sin(heading)))
                    self.descent_turned_90 = True
                    self.descent_go_back_done = False
                    print("DESCENT: TURN 90")
                else:
                    # No improvement after turning 90 degrees, turn 180 degrees (reverse direction)
                    dx, dy = (-self.last_descent_move[0], -self.last_descent_move[1])
                    self.descent_turned_90 = False
                    print("DESCENT: TURN 180")

        # Log the movement decision
        print(f"DESCENT: MOVE ({dx}, {dy})")
        self.last_descent_move = (dx, dy)

        # Check if the robot has reached a key or chest
        if self.cell_val == 1:
            print("DESCENT: SUCCESS!")
            # Reset descent state after success
            self.descent_count = 0
            self.in_descent = False
            self.descent_cooldown = 20
            self.descent_pos = []
            dx, dy = 0, 0  # Stop moving
        else:
            # Handle failure cases or continue the descent
            if self.descent_count > 50:
                # Descent failed after too many attempts
                print("DESCENT: FAILED!")
                self.descent_count = 0
                self.in_descent = False
                self.descent_cooldown = 20
                self.descent_pos = []
                dx, dy = 0, 0  # Stop moving
            else:
                # Increment descent attempt counter
                self.descent_count += 1

        # Return the movement decision
        return (dx, dy)

    
    def move_to(self, obj_type):
        """
        Determines the movement required to reach a specific object of a given type.
        The object's coordinates are assumed to be known via broadcasts, and this function
        computes the direction based on the object's position relative to the robot.
        
        Parameters:
            obj_type (str): The type of object to move to (e.g., key or box).

        Returns:
            tuple: The movement vector as (x, y), where each value is either -1, 0, or 1.
        """
        print("MOVE TO:", obj_type)  # Debug log for the requested object type

        # Determine which map to use based on the object type
        if obj_type == KEY_TYPE:
            obj_map = self.key_map
        else:
            obj_map = self.box_map

        obj_found = False

        # Normalize obj_map to always be a list, even if it's a single dictionary
        if isinstance(obj_map, dict):
            obj_map = [obj_map]

        # Search for the object owned by this agent in the object map
        for obj in obj_map:
            print(f"MOVE TO: OBJ LIST {obj}")  # Debug log for current object in the list
            if obj["owner"] == self.agent_id:  # Check if the object belongs to this robot
                obj_pos = obj["position"]  # Extract the object's position
                obj_found = True
                break  # Exit the loop once the object is found

        # If no object of the desired type is found, return no movement
        if not obj_found:
            print(f"MOVE TO: NO OBJ {obj_type} IN LIST")
            return (0, 0)

        # Calculate the vector to the target object's position
        offset_x, offset_y = obj_pos[0] - self.x, obj_pos[1] - self.y

        first_loop = True
        heading_offset = 0
        x,y = 0,0
        while self.obstacle_map[int(self.x+x),int(self.y+y)] == 1 or first_loop: # avoid obstacle

            # Compute the heading (angle) towards the object and normalize it to a unit vector
            if not first_loop:
                heading_offset += np.pi/90
            
            heading = np.arctan2(offset_y, offset_x) + heading_offset
            x, y = round(np.cos(heading)), round(np.sin(heading))  # Convert heading to discrete movement

            first_loop = False

        

        return (x, y)  # Return the movement vector


    def init_map_portion(self):
        """
        Initializes the portion of the map assigned to this agent for exploration.
        Each agent is responsible for a specific region of the map, determined by 
        dividing the map width among the expected number of agents.

        This function ensures that:
        - The map portion for the agent is set up and marked as initialized.
        - The region assigned to the agent is clearly defined and adjusted for edge cases.

        Returns:
            None
        """
        # Check if the map portion is already initialized
        if self.portion_init:
            return
        else:
            self.portion_init = True  # Mark the portion as initialized

        # Create a map portion filled with zeros (unexplored)
        self.map_portion = np.zeros((self.w, self.h))

        # Calculate the width of the region assigned to each agent
        region_width = max(1, self.w // self.nb_agents_expected)  # Ensure a minimum width of 1

        # Determine the start and end columns for this agent's region
        start_col = self.agent_id * region_width
        end_col = start_col + region_width

        # Ensure the last agent's region covers any remaining columns
        if self.agent_id == self.nb_agents_expected - 1:
            end_col = self.w

        # Adjust indices to ensure they are within map bounds
        start_col = max(0, start_col)
        end_col = min(self.w, end_col)

        # Mark this agent's assigned region as active (value = 1)
        self.map_portion[start_col:end_col, :] = 1


    def update_map_portion(self, obj_pos):
        """
        Updates the map portion to reflect areas explored around the given position.
        A square region centered on the object's position is marked as explored (value = 0).

        Parameters:
            obj_pos (tuple): The (x, y) coordinates of the position to update.

        Returns:
            None
        """
        # Extract x and y coordinates from the object's position
        x, y = obj_pos

        # Define the range around the position to be marked as explored
        EXPLORED_AREA = 2  # Variable defining the explored radius

        self.map_portion[
            max(0, x - EXPLORED_AREA):min(self.map_portion.shape[0], x + EXPLORED_AREA + 1),
            max(0, y - EXPLORED_AREA):min(self.map_portion.shape[1], y + EXPLORED_AREA + 1)
        ] = 0  # Mark the region as explored (value = 0)


    def explore(self):
        """
        Explores the map to find the nearest unexplored pixel and moves towards it.
        If no unexplored pixels are left, exploration is marked as finished.
        The function also handles transitioning into the descent phase if certain conditions are met.

        Returns:
            tuple: The (x, y) direction of the next move.
        """

        # Initialize variables to track the nearest unexplored pixel
        nearest_distance = float('inf')  # Start with an infinite distance
        best_move = None  # Placeholder for the best move
        x, y = 0, 0  # Default movement is stationary

        # Iterate through the map to find the closest unexplored pixel
        for i in range(self.w):  # Loop through map width
            for j in range(self.h):  # Loop through map height
                if self.map_portion[i, j] == 1 :  # Check if the pixel is unexplored and not obstacle
                    # Calculate the Euclidean distance to the unexplored pixel
                    distance = np.sqrt((i - self.x) ** 2 + (j - self.y) ** 2)
                    # calculate custom distance to favor diagonal
                    #distance = min(abs(i - self.x), abs(j - self.y)) + 2 * abs(abs(i - self.x) - abs(j - self.y))
                    if distance < nearest_distance:  # Update if a closer pixel is found
                        
                        dx, dy = i - self.x, j - self.y  # Store the relative move
                        
                        # Normalize the move to a step of 1 in x and y directions
                        x = int(dx / abs(dx)) if dx != 0 else 0
                        y = int(dy / abs(dy)) if dy != 0 else 0

                        if self.obstacle_map[int(self.x+x),int(self.y+y)] == 0: # avoid obstacle
                            nearest_distance = distance
                            best_move = x,y

                        

        # Determine the direction to move towards the nearest unexplored pixel
        if best_move:
            dx, dy = best_move  # Extract the best relative move
            print(f"EXPLORE: BEST MOVE ({best_move})")
            # Normalize the move to a step of 1 in x and y directions
            x = int(dx / abs(dx)) if dx != 0 else 0
            y = int(dy / abs(dy)) if dy != 0 else 0
        else:
            # No unexplored pixels found, exploration is complete
            print("EXPLORE: NO UNEXPLORED PIXELS")
            self.explore_finished = True


        # Handle descent phase
        if self.cell_val != 0 and self.descent_cooldown <= 0:  # Condition to enter descent
            self.in_descent = True  # Enable descent mode
            # Record the starting position and cell value for descent
            self.descent_pos.append((self.x, self.y, self.cell_val))
            self.last_descent_move = (x, y)  # Store the last move direction
            self.descent_go_back_done = False  # Reset go-back status
        else:
            # Decrement descent cooldown if not entering descent
            self.descent_cooldown -= 1
        

        return (x, y)  # Return the computed move direction



    def compute_move(self):
        """
        Computes the next move for the agent based on its current state.
        :return: Coordinates (x, y) for the next move.
        """
        if self.go_back:
            dx,dy = self.last_move
            return (-dx,-dy)
        
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