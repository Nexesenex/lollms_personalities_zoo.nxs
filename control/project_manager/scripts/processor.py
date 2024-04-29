from lollms.helpers import ASCIIColors
from lollms.config import TypedConfig, BaseConfig, ConfigTemplate
from lollms.personality import APScript, AIPersonality
from lollms.utilities import PackageManager
from lollms.types import MSG_TYPE
from typing import Callable

from pathlib import Path
from typing import List
import json
import subprocess
from ascii_colors import trace_exception
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
        # Example entry
        #       {"name":"make_scripted","type":"bool","value":False, "help":"Makes a scriptred AI that can perform operations using python script"},
        # Supported types:
        # str, int, float, bool, list
        # options can be added using : "options":["option1","option2"...]        
        personality_config_template = ConfigTemplate(
            [
                {"name":"nb_attempts","type":"int","value":5, "help":"Maximum number of attempts to summon a member"},
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
                                    "commands": { # list of commands
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

    def mounted(self):
        """
        triggered when mounted
        """
        pass

    def selected(self):
        """
        triggered when mounted
        """
        pass

    def help(self, prompt="", full_context=""):
        self.full(self.personality.help)
    
    def add_file(self, path, client, callback=None):
        """
        Here we implement the file reception handling
        """
        super().add_file(path, client, callback)

    from lollms.client_session import Client
    def run_workflow(self, prompt:str, previous_discussion_text:str="", callback: Callable[[str, MSG_TYPE, dict, list], bool]=None, context_details:dict=None, client:Client=None):
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
                - force_language (str): The force language information.
                - fun_mode (str): The fun mode conditionning text
                - ai_prefix (str): The AI prefix information.
            n_predict (int): The number of predictions to generate.
            client_id: The client ID for code generation.
            callback (function, optional): The callback function for code generation.

        Returns:
            None
        """

        self.callback = callback
        self.personality.info("Generating")
        members:List[AIPersonality] = self.personality.app.mounted_personalities
        output = ""
        
        self.step_start("Making plan")
        attempts = 0
        done =  False
        while attempts<self.personality_config.nb_attempts and not done:
            q_prompt = "\n".join([
                "!@>system:",
                "Utilizing the abilities of a select few team members, devise a strategy to address the issue presented by the user. Engage only the indispensable members to contribute to this solution.",
                "Team members:\n"
            ]) 
            collective_infos = ""
            for i,drone in enumerate(members):
                if drone.name!=self.personality.name:
                    collective_infos +=  f"member id: {i}\n"
                    collective_infos +=  f"member name: {drone.name}\n"
                    collective_infos +=  f"member description: {drone.personality_description[:126]}...\n"
            q_prompt += collective_infos
            answer = ""
            q_prompt += "\n".join([
                "Utilizing the abilities of a select few team members, devise a strategy to address the issue presented by the user.",
                "Engage only the indispensable members to contribute to this solution.",
                "Answer in form of a valid json text in this format:",
                "```json",
                "[",
                "    {",
                '        "member_id":id,'
                '        "task":"task to be done"'
                "    },",
                "    {",
                '        "member_id":id,'
                '        "task":"task to be done"'
                "    }",
                "]",
                "```",
                "Do not add any comments to your answer."
            ])
            q_prompt += f"!@>user:{prompt}\n"
            q_prompt += "\n".join([
                "!@>project_manager_ai:\n"
            ])
            answer = self.fast_gen(q_prompt, 1024, show_progress=True)
            code = self.extract_code_blocks(answer)
            if len(code)>0:
                plan = json.loads(code[0]["content"])
            for member in plan:
                output += "<h2>"+members[member["member_id"]].name+"</h2>"
                output += "<p>"+member["task"]+"</p>"
            q_prompt = prompt
            self.full(output)
            self.step_end("Making plan")

            self.step("Executing plan")
            for step in plan:
                member_id = step["member_id"]
                try:
                    member_id = int(member_id)
                except Exception as ex:
                    self.exception(ex)
                self.step(members[member_id].name)
                attempts = 0
                while attempts<self.personality_config.nb_attempts:
                    try:
                        members[member_id].callback=callback
                        if members[member_id].processor:
                            q_prompt += f"!@>sytsem: Starting task by {members[member_id].name}, provide details\n!@>project_manager_ai: "
                            reformulated_request=self.fast_gen(q_prompt, show_progress=True)
                            members[member_id].new_message("")
                            output = ""
                            self.full(output)
                            previous_discussion_text= previous_discussion_text.replace(prompt,reformulated_request)
                            members[member_id].new_message("")
                            members[member_id].processor.text_files = self.personality.text_files
                            members[member_id].processor.image_files = self.personality.image_files
                            members[member_id].processor.run_workflow(reformulated_request, previous_discussion_text, callback,context_details, client)
                        else:
                            previous_discussion_text_= previous_discussion_text.replace(prompt,"\n".join([
                                "!@>user:",
                                f"{prompt}",
                                "!@>AI name:",
                                members[member_id].name,
                                "!@>task:",
                                step["task"],
                            ]))
                            members[member_id].new_message("")
                            output = members[member_id].generate(previous_discussion_text_,self.personality.config.ctx_size-len(self.personality.model.tokenize(previous_discussion_text)),callback=callback)
                            members[member_id].full(output)
                        break
                    except Exception as ex:
                        trace_exception(ex)
                        self.step("Failed. Retrying...")
                        attempts += 1
        return answer

