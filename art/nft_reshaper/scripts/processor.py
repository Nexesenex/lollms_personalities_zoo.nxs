from lollms.helpers import ASCIIColors
from lollms.config import TypedConfig, BaseConfig, ConfigTemplate
from lollms.personality import APScript, AIPersonality
import subprocess
from pathlib import Path
# Helper functions
import csv
from pathlib import Path
import importlib
import shutil


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
        # Get the current directory
        root_dir = personality.lollms_paths.personal_path
        # We put this in the shared folder in order as this can be used by other personalities.
        shared_folder = root_dir/"shared"
        self.sd_folder = shared_folder / "auto_sd"    
        self.output_folder = personality.lollms_paths.personal_outputs_path/"nft_reshaper"
        self.output_folder.mkdir(parents=True, exist_ok=True)
        # Example entry
        #       {"name":"make_scripted","type":"bool","value":False, "help":"Makes a scriptred AI that can perform operations using python script"},
        # Supported types:
        # str, int, float, bool, list
        # options can be added using : "options":["option1","option2"...]
        personality_config_template = ConfigTemplate(
            [
                {"name":"folder_path","type":"str","value":"", "help":"The folder containing the files of the nft collection"},
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
        self.sd = None
        
    def install(self):
        super().install()
        
        requirements_file = self.personality.personality_package_path / "requirements.txt"
        # Install dependencies using pip from requirements.txt
        subprocess.run(["pip", "install", "--upgrade", "-r", str(requirements_file)])      
        ASCIIColors.success("Installed successfully")

    def help(self, prompt="", full_context=""):
        self.full(self.personality.help)
    
    def add_file(self, path, callback=None):
        """
        Here we implement the file reception handling
        """
        super().add_file(path, callback)

    def get_sd(self):
        sd_script_path = self.sd_folder / "lollms_sd.py"
        
        if sd_script_path.exists():
            ASCIIColors.success("lollms_sd found.")
            ASCIIColors.success("Loading source file...",end="")
            module_name = sd_script_path.stem  # Remove the ".py" extension
            # use importlib to load the module from the file path
            loader = importlib.machinery.SourceFileLoader(module_name, str(sd_script_path))
            ASCIIColors.success("ok")
            ASCIIColors.success("Loading module...",end="")
            sd_module = loader.load_module()
            ASCIIColors.success("ok")
            return sd_module
        
    def prepare(self):
        if self.sd is None:
            self.step_start("Loading ParisNeo's fork of AUTOMATIC1111's stable diffusion service")
            self.sd = self.get_sd().LollmsSD(self.personality.lollms_paths, "Artbot", max_retries=-1)
            self.step_end("Loading ParisNeo's fork of AUTOMATIC1111's stable diffusion service")

    def create_csv_from_folder(self, path):
        counter = 1
        rows = []
        
        folder_path = Path(path)
        all_descriptions=""
        for file_path in folder_path.glob('*.png'):
            name = file_path.stem
            filename = file_path.name
            shutil.copy(file_path, self.output_folder/filename)

            external_url = ""
            self.step_start(f"Processing : {name}")
            description = self.sd.interrogate(str(file_path)).info
            self.print_prompt("Blip description",description)

            description = self.fast_gen(f"@!>Instruction:Make a description of this png file: {filename} out of the fast description and the file name.\n@!>Fast description:{description}\n@!>Description:",256).replace("\"","")
            style_collection = file_path.parent.name
            all_descriptions += f"## {name}\n![](outputs/nft_reshaper/{filename})\n{description}\n"
            self.full(all_descriptions)
            rows.append([counter, name, description, filename, external_url, style_collection])
            self.step_end(f"Processing : {name}")
            counter += 1
        
        with open(file_path.parent/"metadata.csv", "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["tokenID", "name", "description", "file_name", "external_url", "attributes[style_collection]"])
            writer.writerows(rows)
    def run_workflow(self, prompt, previous_discussion_text="", callback=None):
        """
        Runs the workflow for processing the model input and output.

        This method should be called to execute the processing workflow.

        Args:
            prompt (str): The input prompt for the model.
            previous_discussion_text (str, optional): The text of the previous discussion. Default is an empty string.
            callback a callback function that gets called each time a new token is received
        Returns:
            None
        """
        self.callback = callback
        self.prepare()

        if self.personality_config.folder_path!="":
            self.create_csv_from_folder(self.personality_config.folder_path)
        else:
            self.full("Please specify a valid folder path in the configurations of the personality")
        return ""
