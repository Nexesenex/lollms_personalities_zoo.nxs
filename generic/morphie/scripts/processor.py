"""
project: lollms
personality: # Place holder: Personality name 
Author: # Place holder: creator name 
description: # Place holder: personality description
"""
from lollms.types import MSG_OPERATION_TYPE
from lollms.helpers import ASCIIColors
from lollms.config import TypedConfig, BaseConfig, ConfigTemplate
from lollms.personality import APScript, AIPersonality
import subprocess
from typing import Callable, Any

# Helper functions
class Processor(APScript):
    """
    A class that processes model inputs and outputs.

    Inherits from APScript.
    """
    def __init__(
                 self, 
                 personality: AIPersonality,
                 callback = None,
                ) -> None:
        
        self.callback = None
        # Example entries
        #       {"name":"make_scripted","type":"bool","value":False, "help":"Makes a scriptred AI that can perform operations using python script"},
        #       {"name":"make_scripted","type":"bool","value":False, "help":"Makes a scriptred AI that can perform operations using python script"},
        # Supported types:
        # str, int, float, bool, list
        # options can be added using : "options":["option1","option2"...]        
        personality_config_template = ConfigTemplate(
            [
                {"name":"conditionning","type":"text","value":"Act as a helpful assistant.", "help":"Makes a scriptred AI that can perform operations using python script"},
                {"name":"temperature","type":"float", "min":0.1, "max":2,"value":False, "help":"Temperature of the answer (higher value gives more liberty to the AI, lower value makes the output more deterministic). Values over 1 may be unstable. It is advised not to go beyond 0.9 but you can try that for fun"},
                {"name":"accept_documentation","type":"bool","value":False, "help":"Accept documentation"},
                {"name":"accept_internet","type":"bool","value":False, "help":"Accept internet"},
                {"name":"accept_knowledge","type":"bool","value":False, "help":"Accept knowledge"},
                
            ]
            )
        personality_config_vals = BaseConfig.from_template(personality_config_template)

        personality_config = TypedConfig(
            personality_config_template,
            personality_config_vals
        )
        super().__init__(
                            personality,
                            personality_config,
                            [
                                {
                                    "name": "idle",
                                    "commands": { # list of commands (don't forget to add these to your config.yaml file)
                                        "help":self.help,
                                    },
                                    "default": None
                                },                           
                            ],
                            callback=callback
                        )
        
    def install(self):
        super().install()
        
        # requirements_file = self.personality.personality_package_path / "requirements.txt"
        # Install dependencies using pip from requirements.txt
        # subprocess.run(["pip", "install", "--upgrade", "-r", str(requirements_file)])      
        ASCIIColors.success("Installed successfully")        

    def help(self, prompt="", full_context=""):
        self.set_message_content(self.personality.help)
    
    def add_file(self, path, client, callback=None):
        """
        Here we implement the file reception handling
        """
        super().add_file(path, client, callback)

    from lollms.client_session import Client
    def run_workflow(self, prompt:str, previous_discussion_text:str="", callback: Callable[[str | list | None, MSG_OPERATION_TYPE, str, AIPersonality| None], bool]=None, context_details:dict=None, client:Client=None):
        """
        This function generates code based on the given parameters.

        Args:
            full_prompt (str): The full prompt for code generation.
            prompt (str): The prompt for code generation.
            context_details (dict): A dictionary containing the following context details for code generation:
                - conditionning (str): The conditioning information.
                - documentation (str): The documentation information.
                - knowledge (str): The knowledge information.
                - user_description (str): The user description information.
                - discussion_messages (str): The discussion messages information.
                - positive_boost (str): The positive boost information.
                - negative_boost (str): The negative boost information.
                - current_language (str): The force language information.
                - fun_mode (str): The fun mode conditionning text
                - ai_prefix (str): The AI prefix information.
            n_predict (int): The number of predictions to generate.
            client_id: The client ID for code generation.
            callback (function, optional): The callback function for code generation.

        Returns:
            None
        """
        self.personality.info("Generating")
        self.callback = callback
        prompt = self.build_prompt([
            self.personality_config.conditionning,
            context_details["documentation"] if self.personality_config.accept_documentation else "",
            context_details["knowledge"] if self.personality_config.accept_knowledge else "",
            "\n".join([f"internet result at {i}:\n{c}" for i, c in zip(context_details["internet_search_infos"],context_details["internet_search_results"])]) if self.personality_config.accept_internet else "",
            context_details["discussion_messages"],
            
        ])
        self.personality.model_temperature = float(self.personality_config.temperature)
        
        ASCIIColors.cyan(prompt)
        out = self.fast_gen(prompt)
        self.set_message_content(out)
        return out

