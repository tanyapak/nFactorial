import arcade
import os
import pickle

# --- Constants
SCREEN_TITLE = "Platformer"

SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 768 # NUMBER_OF_TILES x TILE_SCALING x 16
CHARACTER_BUFFER = 100

# Constants used to scale our sprites from their original size
CHARACTER_SCALING = 4
TILE_SCALING = 4
COIN_SCALING = 0.5
SPRITE_PIXEL_SIZE = 16
GRID_PIXEL_SIZE = SPRITE_PIXEL_SIZE * TILE_SCALING

# Movement speed of player, in pixels per frame
PLAYER_MOVEMENT_SPEED = 5
GRAVITY = 1
PLAYER_JUMP_SPEED = 20

class Player(arcade.Sprite):
    def __init__(self, textures, state="idle", scale=1.0):
        super().__init__(texture=textures["idle"][0][0], scale=scale)
        self.texture_dict = textures
        self.textures, self.textures_mirrored = zip(*textures[state])
        self.state = state
        self.current_frame = 0
        self.texture_change_tick = 0
        self.texture_change_rate = 10  # Change this to control the animation speed
        self.facing_right = True
        self.physics_engine = None
        self.on_special_surface = False
        self.can_update_state = True
        self.hit_object = False
        
    def update_state(self, state):
        if self.can_update_state:  # Check if the state can be updated
            self.state = state
            self.textures, self.textures_mirrored = zip(*self.texture_dict[state])
            self.current_frame = 0

    def update_state_on_ground(self, physics_engine):
        if physics_engine.can_jump() and self.change_x == 0 and self.change_y == 0:
            self.update_state("idle")

    def update(self):
        self.texture_change_tick += 1
        if self.texture_change_tick >= self.texture_change_rate:
            self.texture_change_tick = 0
            self.current_frame += 1
            if self.current_frame >= len(self.textures):
                self.current_frame = 0
                # Stop attack if animation is dones
                if self.state == "attack":
                    self.can_update_state = True  # Set to True when the attack animation is finished
                    self.update_state("idle")
            self.texture = self.textures[self.current_frame] if self.facing_right else self.textures_mirrored[self.current_frame]

        # Call the new method to update the player's state based on their position and movement
        if self.state == "jump" and hasattr(self, "physics_engine"):
            self.update_state_on_ground(self.physics_engine)

class MyGame(arcade.Window):
    """
    Main application class.
    """

    def __init__(self):

        # Call the parent class and set up the window
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT,
                         SCREEN_TITLE, resizable=True)g

        # Our TileMap Object
        self.tile_map = None

        # Our Scene Object
        self.scene = None

        # Separate variable that holds the player sprite
        self.player_sprite_1 = None
        self.player_sprite_2 = None

        # Our physics engine
        self.physics_engine_1 = None
        self.physics_engine_2 = None

        # A Camera that can be used for scrolling the screen
        self.camera_sprites = None

        # A non-scrolling camera that can be used to draw GUI elements
        self.camera_gui = None

        # Keep track of the score
        self.score = 0

        # What key is pressed down?
        self.left_key_down_1 = False
        self.right_key_down_1 = False

        self.left_key_down_2 = False
        self.right_key_down_2 = False

        # Players' positions - to add constraints
        self.player_initial_position = None

        # Add a new attribute to track the object removal delay
        self.object_removal_delay_1 = None
        self.object_removal_delay_2 = None

        self.end_of_map = 0

        # Current level
        self.current_level = 0

        # Between levels
        self.between_levels = True

        # Game end
        self.game_end = False

        # Game state variable
        self.game_state = "RUNNING"

        # Save message timer and duration
        self.save_message_timer = 0
        self.save_message_duration = 2.0  # 2 seconds

        # Load message timer and duration
        self.load_message_timer = 0
        self.load_message_duration = 2.0  # 2 seconds

        # Sounds
        self.lever1_sound_played = False
        self.lever2_sound_played = False
        self.end_sound_played = False

    def load_textures(self, path):
        texture_dict = {"idle": [], "walk": [], "jump": [], "surf": [], "attack": []}
        for state in texture_dict.keys():
            frame_index = 1
            while True:
                try:
                    texture = arcade.load_texture_pair(f"{path}/{state}/{state}_{frame_index}.png")
                    texture_dict[state].append(texture)
                    frame_index += 1
                except FileNotFoundError:
                    break
        return texture_dict

    def setup(self):
        """Set up the game here. Call this function to restart the game."""

        # Setup the Cameras
        self.camera_sprites = arcade.Camera(self.width, self.height)
        self.camera_gui = arcade.Camera(self.width, self.height)

        # Keep track of the score
        self.score = 0

        # Set up the players, specifically placing it at these coordinates.
        self.players_list = arcade.SpriteList()
        textures_1 = self.load_textures(os.path.join("characters", "fireboy"))
        self.player_sprite_1 = Player(textures_1, scale=CHARACTER_SCALING)
        
        textures_2 = self.load_textures(os.path.join("characters", "watergirl"))
        self.player_sprite_2 = Player(textures_2, scale=CHARACTER_SCALING)

        # Set initial state for each character
        self.player_sprite_1.state = "idle"
        self.player_sprite_2.state = "idle"

        # Store characters' initial positions
        self.player_initial_position = min(self.player_sprite_1.left, self.player_sprite_2.left)

        # Set up the level
        self.current_level = 1
        self.setup_level(self.current_level)
        
    def setup_level(self, level):
        # Clean up previous level's resources
        if hasattr(self, "scene") and self.scene is not None:
            for layer in self.scene.sprite_lists:
                for sprite in layer:
                    sprite.remove_from_sprite_lists()

        # Name of map file to load
        map_name = f"maps/map-level{level}.json"

        # Layer specific options are defined based on Layer names in a dictionary
        # Doing this will make the SpriteList for the platforms layer
        # use spatial hashing for detection.
        layer_options = {
            "Platforms": {
                "use_spatial_hash": True,
            },
        }

        # Read in the tiled map
        self.tile_map = arcade.load_tilemap(map_name, TILE_SCALING, layer_options)

        # Calculate the right edge of the my_map in pixels
        self.end_of_map = self.tile_map.width * GRID_PIXEL_SIZE

        # Initialize Scene with our TileMap, this will automatically add all layers
        # from the map as SpriteLists in the scene in the proper order.
        self.scene = arcade.Scene.from_tilemap(self.tile_map)

        # Set the background color
        if self.tile_map.background_color:
            arcade.set_background_color(self.tile_map.background_color)

        if level == 1:
            music1 = arcade.sound.load_sound("sounds/music.wav")
            arcade.Sound.play(music1, volume=0.2, loop=True)
            self.player_sprite_1.center_x = 360
            self.player_sprite_1.center_y = SCREEN_HEIGHT

            self.player_sprite_2.center_x = 480
            self.player_sprite_2.center_y = SCREEN_HEIGHT

            self.physics_engine_1 = arcade.PhysicsEnginePlatformer(
                self.player_sprite_1, gravity_constant=GRAVITY, walls=[self.scene["Platforms"], self.scene["Water Wall"]]
            )
            self.physics_engine_2 = arcade.PhysicsEnginePlatformer(
                self.player_sprite_2, gravity_constant=GRAVITY, walls=[self.scene["Platforms"], self.scene["Water"], self.scene["Fire Wall"]]
            )
        elif level == 2:
            self.player_sprite_1.center_x = 200
            self.player_sprite_1.center_y = SCREEN_HEIGHT

            self.player_sprite_2.center_x = 300
            self.player_sprite_2.center_y = SCREEN_HEIGHT

            self.physics_engine_1 = arcade.PhysicsEnginePlatformer(
                self.player_sprite_1, gravity_constant=GRAVITY, walls=[self.scene["Platforms"], self.scene["Bridge"], self.scene["Wall"], self.scene["Wall2"], self.scene["Water Frozen"], self.scene["Walls"]]
            )
            self.physics_engine_2 = arcade.PhysicsEnginePlatformer(
                self.player_sprite_2, gravity_constant=GRAVITY, walls=[self.scene["Platforms"], self.scene["Bridge"], self.scene["Wall"], self.scene["Wall2"], self.scene["Water Frozen"], self.scene["Walls"]]
            )

        self.scene.add_sprite("Player", self.player_sprite_1)
        self.scene.add_sprite("Player", self.player_sprite_2)

        self.player_sprite_1.physics_engine = self.physics_engine_1
        self.player_sprite_2.physics_engine = self.physics_engine_2

    def on_draw(self):
        """Render the screen."""
        
        # This command has to happen before we start drawing
        arcade.start_render()

        if not self.game_end:
            # Draw the instructions between levels
            if self.between_levels:
                if self.current_level == 1:
                    arcade.draw_text("Chapter 1: Crystal Caves", SCREEN_WIDTH // 2, SCREEN_HEIGHT-150, arcade.color.WHITE, 80, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("HOW TO PLAY", SCREEN_WIDTH // 2, SCREEN_HEIGHT-300, arcade.color.WHITE, 64, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("1. Fire Knight uses (Left, Right, Up) to move and jump.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-400, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("2. Water Priestess uses (A, D, W) to move and jump.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-450, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("3. Fire Knight can walk through fire.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-500, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("Water Priestess can walk on water.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-550, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("Not vice versa.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-600, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")

                    arcade.draw_text("Press ENTER to continue", SCREEN_WIDTH // 2, 30, arcade.color.WHITE, 48, anchor_x="center", font_name="Kenney Pixel")
                else:
                    arcade.draw_text("Chapter 2: Forest of Illusion", SCREEN_WIDTH // 2, SCREEN_HEIGHT-150, arcade.color.WHITE, 80, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("SPECIAL ATTACK UNLOCKED!", SCREEN_WIDTH // 2, SCREEN_HEIGHT-300, arcade.color.WHITE, 64, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("1. Fire Knight's special attack is activated by", SCREEN_WIDTH // 2, SCREEN_HEIGHT-400, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("pressing RSHIFT and can clear out debris.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-450, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("2. Water Priestess's special attack is activated by", SCREEN_WIDTH // 2, SCREEN_HEIGHT-500, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")
                    arcade.draw_text("pressing LSHIFT and can freeze bodies of water.", SCREEN_WIDTH // 2, SCREEN_HEIGHT-550, arcade.color.WHITE, 36, anchor_x="center", font_name="Kenney Pixel")

                    arcade.draw_text("Press ENTER to continue", SCREEN_WIDTH // 2, 30, arcade.color.WHITE, 48, anchor_x="center", font_name="Kenney Pixel")

            else:
                # Clear the screen to the background color
                self.clear()

                # Activate the game camera
                self.camera_sprites.use()

                # Draw our Scene
                # Note, if you a want pixelated look, add pixelated=True to the parameters
                self.scene.draw(pixelated=True)

                # Activate the GUI camera before drawing GUI elements
                self.camera_gui.use()

                # Draw our score on the screen, scrolling it with the viewport
                score_text = f"Score: {self.score}"
                arcade.draw_text(score_text,
                                start_x=32,
                                start_y=32,
                                color=arcade.csscolor.WHITE,
                                font_size=48, font_name="Kenney Pixel")
                                
                if self.game_state == "PAUSED":
                    # Draw pause sign/message
                    x = SCREEN_WIDTH // 2
                    y = SCREEN_HEIGHT // 2
                    arcade.draw_text("PAUSED", x, y, arcade.csscolor.WHITE, 64, anchor_x="center", anchor_y="center", font_name="Kenney Pixel")

                if self.save_message_timer > 0:
                    x = SCREEN_WIDTH // 2
                    y = SCREEN_HEIGHT - 50
                    arcade.draw_text("SAVED", x, y, arcade.csscolor.WHITE, 64, anchor_x="center", anchor_y="center", font_name="Kenney Pixel")

                if self.load_message_timer > 0:
                    x = SCREEN_WIDTH // 2
                    y = SCREEN_HEIGHT - 100  # Adjust the position so it does not overlap with the save message
                    arcade.draw_text("LOADED", x, y, arcade.csscolor.WHITE, 64, anchor_x="center", anchor_y="center", font_name="Kenney Pixel")
                            
        # Draw game over message if the game has ended
        else:
            arcade.draw_text("The End", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2,
                            arcade.color.WHITE, 96, anchor_x="center", font_name="Kenney Pixel")

            arcade.draw_text("YOU SUCCESSFULLY COMPLETED THE GAME!",
                            SCREEN_WIDTH // 2, (SCREEN_HEIGHT // 2) - 72,
                            arcade.color.WHITE, 48, anchor_x="center", font_name="Kenney Pixel")

            arcade.draw_text(f"YOUR SCORE: {self.score}",
                            SCREEN_WIDTH // 2, (SCREEN_HEIGHT // 2) - 240,
                            arcade.color.WHITE, 48, anchor_x="center", font_name="Kenney Pixel")

    def update_player_speed(self):
        # Calculate speed based on the keys pressed
        self.player_sprite_1.change_x = 0
        self.player_sprite_2.change_x = 0

        if self.left_key_down_1 and not self.right_key_down_1:
            self.player_sprite_1.change_x = -PLAYER_MOVEMENT_SPEED
        elif self.right_key_down_1 and not self.left_key_down_1:
            self.player_sprite_1.change_x = PLAYER_MOVEMENT_SPEED

        if self.left_key_down_2 and not self.right_key_down_2:
            self.player_sprite_2.change_x = -PLAYER_MOVEMENT_SPEED
        elif self.right_key_down_2 and not self.left_key_down_2:
            self.player_sprite_2.change_x = PLAYER_MOVEMENT_SPEED

        # Check if players are on the ground and not moving, then set their state to idle
        if self.physics_engine_1.can_jump() and self.player_sprite_1.change_x == 0:
            self.player_sprite_1.update_state("idle")
        if self.physics_engine_2.can_jump() and self.player_sprite_2.change_x == 0:
            self.player_sprite_2.update_state("idle")

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed."""
        # Handle pausing
        if key == arcade.key.P:
            if self.game_state == "RUNNING":
                self.game_state = "PAUSED"
            elif self.game_state == "PAUSED":
                self.game_state = "RUNNING"

        # Handle saving the game
        if key == arcade.key.S and modifiers == arcade.key.MOD_CTRL:
            self.save_game('savegame.pickle')

        # Handle loading the game
        if key == arcade.key.L and modifiers == arcade.key.MOD_CTRL:
            self.load_game('savegame.pickle')

        if self.between_levels:
            if key == arcade.key.ENTER:
                self.between_levels = False
                # self.setup_level(self.current_level)
        
        # Jump Player 1
        if key == arcade.key.UP:
            if self.physics_engine_1.can_jump():
                self.player_sprite_1.change_y = PLAYER_JUMP_SPEED
                self.player_sprite_1.update_state("jump")
                arcade.play_sound(arcade.sound.load_sound(':resources:sounds/jump3.wav'))
        # Left Player 1
        if key == arcade.key.LEFT:
            self.left_key_down_1 = True
            self.player_sprite_1.facing_right = False
            self.update_player_speed()
            if self.physics_engine_1.can_jump():  # Check if the player is not on the ground
                if self.player_sprite_1.on_special_surface:
                    self.player_sprite_1.update_state("surf")
                else:
                    self.player_sprite_1.update_state("walk")
        # Right Player 1
        elif key == arcade.key.RIGHT:
            self.right_key_down_1 = True
            self.player_sprite_1.facing_right = True
            self.update_player_speed()
            if self.physics_engine_1.can_jump():  # Check if the player is not on the ground
                if self.player_sprite_1.on_special_surface:
                    self.player_sprite_1.update_state("surf")
                else:
                    self.player_sprite_1.update_state("walk")
        # Attack Player 1
        if key == arcade.key.RSHIFT and self.current_level == 2:
            self.player_sprite_1.update_state("attack")
            self.player_sprite_1.can_update_state = False  # Set to False when attack is initiated
        
        # Jump Player 2
        if key == arcade.key.W:
            if self.physics_engine_2.can_jump():
                self.player_sprite_2.change_y = PLAYER_JUMP_SPEED
                self.player_sprite_2.update_state("jump")
                arcade.play_sound(arcade.sound.load_sound(':resources:sounds/jump3.wav'))
        # Left Player 2
        if key == arcade.key.A:
            self.left_key_down_2 = True
            self.player_sprite_2.facing_right = False
            self.update_player_speed()
            if self.physics_engine_2.can_jump():  # Check if the player is not on the ground
                if self.player_sprite_2.on_special_surface:
                    self.player_sprite_2.update_state("surf")
                else:
                    self.player_sprite_2.update_state("walk")
        # Right Player 2
        elif key == arcade.key.D:
            self.right_key_down_2 = True
            self.player_sprite_2.facing_right = True
            self.update_player_speed()
            if self.physics_engine_2.can_jump():  # Check if the player is not on the ground
                if self.player_sprite_2.on_special_surface:
                    self.player_sprite_2.update_state("surf")
                else:
                    self.player_sprite_2.update_state("walk")
        # Attack Player 2
        if key == arcade.key.LSHIFT and self.current_level == 2:
            self.player_sprite_2.update_state("attack")
            self.player_sprite_2.can_update_state = False  # Set to False when attack is initiated

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key."""
        if key == arcade.key.LEFT:
            self.left_key_down_1 = False
            self.update_player_speed()
            self.player_sprite_1.update_state("idle")
        elif key == arcade.key.RIGHT:
            self.right_key_down_1 = False
            self.update_player_speed()
            self.player_sprite_1.update_state("idle")
        if key == arcade.key.A:
            self.left_key_down_2 = False
            self.update_player_speed()
            self.player_sprite_2.update_state("idle")
        elif key == arcade.key.D:
            self.right_key_down_2 = False
            self.update_player_speed()
            self.player_sprite_2.update_state("idle")

    def center_camera_to_player(self):
        # Calculate the distance between the two characters
        distance = abs(self.player_sprite_1.center_x - self.player_sprite_2.center_x)

        # Only update the camera position if the distance is less than the window width
        if distance < self.camera_sprites.viewport_width - CHARACTER_BUFFER:
            # Find where both players are, then calculate lower left corner from the average position
            screen_center_x = (self.player_sprite_1.center_x + self.player_sprite_2.center_x) / 2 - (self.camera_sprites.viewport_width / 2)
            # screen_center_y = (self.player_sprite_1.center_y + self.player_sprite_2.center_y) / 2 - (self.camera_sprites.viewport_height / 2)

            # Set some limits on how far we scroll
            if screen_center_x < 0:
                screen_center_x = 0
            
            # Add a condition to limit the camera's position based on the map width
            elif screen_center_x > self.end_of_map - self.camera_sprites.viewport_width:
                screen_center_x = self.end_of_map - self.camera_sprites.viewport_width

            # Here's our center, move to it
            player_centered = screen_center_x, 0
            self.camera_sprites.move_to(player_centered)

        else:
            # Get the camera position (top-left corner coordinates)
            camera_x, camera_y = self.camera_sprites.position

            # Constrain character movement to the camera view
            screen_left = camera_x
            screen_right = camera_x + self.camera_sprites.viewport_width
            # Character 1 constraints
            if self.player_sprite_1.left < screen_left:
                self.player_sprite_1.left = screen_left
            if self.player_sprite_1.right > screen_right:
                self.player_sprite_1.right = screen_right

            # Character 2 constraints
            if self.player_sprite_2.left < screen_left:
                self.player_sprite_2.left = screen_left
            if self.player_sprite_2.right > screen_right:
                self.player_sprite_2.right = screen_right

    def on_update(self, delta_time):

        if self.game_state == "PAUSED":
            return

        # Update the save message timer
        if self.save_message_timer > 0:
            self.save_message_timer -= delta_time

        # Update the load message timer
        if self.load_message_timer > 0:
            self.load_message_timer -= delta_time

        """Movement and game logic"""

        # Check if the characters are within the borders and adjust their position if necessary
        if self.player_sprite_1.left < self.player_initial_position:
            self.player_sprite_1.left = self.player_initial_position
        if self.player_sprite_1.right > self.end_of_map:
            self.player_sprite_1.right = self.end_of_map

        if self.player_sprite_2.left < self.player_initial_position:
            self.player_sprite_2.left = self.player_initial_position
        if self.player_sprite_2.right > self.end_of_map:
            self.player_sprite_2.right = self.end_of_map

        # Check if Player can move past water

        # Update the players
        self.player_sprite_1.update()
        self.player_sprite_2.update()

        # Move the player with the physics engine
        self.physics_engine_1.update()
        self.physics_engine_2.update()

        if self.current_level == 1:
            # See if player is on special surface
            if self.player_sprite_1.center_x > 2240 and self.player_sprite_1.center_x < 2560 and self.scene["Fire Wall"]:
                self.player_sprite_1.on_special_surface = True
            else:
                self.player_sprite_1.on_special_surface = False

            if self.player_sprite_2.center_x > 768 and self.player_sprite_2.center_x < 1216 and self.scene["Bridge"]:
                self.player_sprite_2.on_special_surface = True
            else:
                self.player_sprite_2.on_special_surface = False

            # See if layers were turned
            lever_hit_list_1 = arcade.check_for_collision_with_list(
                self.player_sprite_1, self.scene["Fire Lever"]
            )
            if lever_hit_list_1:
                if not self.lever1_sound_played:
                    arcade.play_sound(arcade.sound.load_sound(':resources:sounds/hit5.wav'))
                    self.lever1_sound_played = True
                for unturned_lever in self.scene["Fire Lever"]:
                    unturned_lever.alpha = 0
                for turned_lever in self.scene["Fire Lever Turned"]:
                    turned_lever.alpha = 255
                for fire in self.scene["Fire"]:
                    fire.remove_from_sprite_lists()
                for fire in self.scene["Fire2"]:
                    fire.remove_from_sprite_lists()
                for wall in self.scene["Fire Wall"]:
                    wall.remove_from_sprite_lists()

            lever_hit_list_2 = arcade.check_for_collision_with_list(
                self.player_sprite_2, self.scene["Water Lever"]
            )
            if lever_hit_list_2:
                if not self.lever2_sound_played:
                    arcade.play_sound(arcade.sound.load_sound(':resources:sounds/hit5.wav'))
                    self.lever2_sound_played = True
                for unturned_lever in self.scene["Water Lever"]:
                    unturned_lever.alpha = 0
                for turned_lever in self.scene["Water Lever Turned"]:
                    turned_lever.alpha = 255
                for bridge in self.scene["Bridge"]:
                    bridge.alpha = 255
                    bridge.remove_from_sprite_lists()
                    self.scene.add_sprite("Platforms", bridge)
                for wall in self.scene["Water Wall"]:
                    wall.remove_from_sprite_lists()

        if self.current_level == 2:
            # Check if Player 1 is using a special attack
            if not self.player_sprite_1.can_update_state:
                object_hit_list = arcade.check_for_collision_with_list(self.player_sprite_1, self.scene["Wall Plants"])
                if object_hit_list and self.player_sprite_1.facing_right:
                    self.player_sprite_1.hit_object = True

            if self.player_sprite_1.can_update_state and self.player_sprite_1.hit_object:
                for wall in list(self.scene["Wall"]):
                    wall.remove_from_sprite_lists()
                for layer_name in ["Plants", "Plants2", "Plants3"]:
                    for plant in self.scene[layer_name]:
                        plant.alpha = 0
                self.player_sprite_1.hit_object = False

            # Check if Player 2 is using a special attack
            if not self.player_sprite_2.can_update_state:
                # Assuming the object is in the "Your_Object_Layer" layer
                object_hit_list = arcade.check_for_collision_with_list(self.player_sprite_2, self.scene["Wall Water"])
                if object_hit_list and self.player_sprite_2.facing_right:
                    self.player_sprite_2.hit_object = True

            if self.player_sprite_2.can_update_state and self.player_sprite_2.hit_object:
                for wall in list(self.scene["Wall2"]):
                    wall.remove_from_sprite_lists()
                for water in self.scene["Water"]:
                    water.alpha = 0
                for layer_name in ["Water Frozen", "Water Frozen2", "Water Frozen3"]:
                    for water in self.scene[layer_name]:
                        water.alpha = 255
                self.player_sprite_2.hit_object = False

        # See if we hit any coins
        coin_hit_list_1 = arcade.check_for_collision_with_list(
            self.player_sprite_1, self.scene["Coins"]
        )

        # Loop through each coin we hit (if any) and remove it
        for coin in coin_hit_list_1:
            # Remove the coin
            coin.remove_from_sprite_lists()
            # Add one to the score
            self.score += 1
            arcade.play_sound(arcade.sound.load_sound(':resources:sounds/coin5.wav'))

        coin_hit_list_2 = arcade.check_for_collision_with_list(
            self.player_sprite_2, self.scene["Coins"]
        )

        for coin in coin_hit_list_2:
            coin.remove_from_sprite_lists()
            self.score += 1
            arcade.play_sound(arcade.sound.load_sound(':resources:sounds/coin5.wav'))

        # See if we characters reach the exit
        exit_hit_list_1 = arcade.check_for_collision_with_list(
            self.player_sprite_1, self.scene["Exit"]
        )
        exit_hit_list_2 = arcade.check_for_collision_with_list(
            self.player_sprite_2, self.scene["Exit"]
        )
        if exit_hit_list_1 and exit_hit_list_2:
            if self.current_level == 1:
                arcade.play_sound(arcade.sound.load_sound(':resources:sounds/upgrade5.wav'))
            else:
                if not self.end_sound_played:
                    arcade.play_sound(arcade.sound.load_sound(':resources:sounds/upgrade5.wav'))
                    self.end_sound_played = True
            if self.current_level == 2:
                self.game_end = True
            else:
                self.current_level += 1
                self.between_levels = True
                self.setup_level(self.current_level)
                
        # Position the camera
        self.center_camera_to_player()

    def on_resize(self, width, height):
        """ Resize window """
        self.camera_sprites.resize(int(width), int(height))
        self.camera_gui.resize(int(width), int(height))

    def save_game(self, filename):
        game_data = {
            'score': self.score,
            'player_initial_position': self.player_initial_position,
            'end_of_map': self.end_of_map,
            'current_level': self.current_level,
            'between_levels': self.between_levels,
            'game_end': self.game_end,
            'game_state': self.game_state,
            'player_position_1': (self.player_sprite_1.center_x, self.player_sprite_1.center_y),
            'player_position_2': (self.player_sprite_2.center_x, self.player_sprite_2.center_y),
        }

        with open(filename, 'wb') as file:
            pickle.dump(game_data, file)

        # Start the save message timer
        self.save_message_timer = self.save_message_duration

    def load_game(self, filename):
        try:
            with open(filename, 'rb') as file:
                game_data = pickle.load(file)

            self.current_level = game_data['current_level']

            # Recreate the TileMap, Scene, Physics Engine objects based on the current level
            self.setup_level(self.current_level)

            self.score = game_data['score']
            self.player_initial_position = game_data['player_initial_position']
            self.end_of_map = game_data['end_of_map']
            self.between_levels = game_data['between_levels']
            self.game_end = game_data['game_end']
            self.game_state = game_data['game_state']

            player_x_1, player_y_1 = game_data['player_position_1']
            self.player_sprite_1.center_x = player_x_1
            self.player_sprite_1.center_y = player_y_1

            player_x_2, player_y_2 = game_data['player_position_2']
            self.player_sprite_2.center_x = player_x_2
            self.player_sprite_2.center_y = player_y_2

        except FileNotFoundError:
            print(f"Error: {filename} not found.")
            return

        # Start the load message timer
        self.load_message_timer = self.load_message_duration

def main():
    """Main function"""
    window = MyGame()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()