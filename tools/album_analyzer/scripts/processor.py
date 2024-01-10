from lollms.helpers import ASCIIColors
from lollms.config import TypedConfig, BaseConfig, ConfigTemplate
from lollms.personality import APScript, AIPersonality
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from lollms.services.sd.lollms_sd import LollmsSD
import subprocess

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
        self.sd = None
        self.callback = None
        # Example entry
        #       {"name":"make_scripted","type":"bool","value":False, "help":"Makes a scriptred AI that can perform operations using python script"},
        # Supported types:
        # str, int, float, bool, list
        # options can be added using : "options":["option1","option2"...]        
        personality_config_template = ConfigTemplate(
            [
                {"name":"album_folder_path","type":"str","value":"", "help":"The folder where to search for files"},
                {"name":"save_in_metadata","type":"bool","value":True, "help":"Saves the description to the metadatas of the file"},
                {"name":"save_in_separate_text_file","type":"bool","value":False, "help":"Saves the description to a text file with the same name as the image file"},
                {"name":"save_in_csv_file","type":"bool","value":False, "help":"Saves add descriptions to a csv file"},
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
                                        "start":self.start,
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
        self.full(self.personality.help)

    def display_folder_structure(self, folder_path):
        folder_path = Path(folder_path)
        tree = ''
        
        for item in folder_path.glob('**/*'):
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                indent = len(item.relative_to(folder_path).parts) - 1
                tree += f"{'    ' * indent}|- {item.name}\n"
        
        return tree

    def process_images(self):
        self.step_start("Scanning folder")
        structure = "## Structure:\n"+self.display_folder_structure(self.personality_config.album_folder_path)
        self.full(structure)
        self.step_end("Scanning folder")

        self.step_start("Building photos metadata")
        self.add_metadata_to_images(self.personality_config.album_folder_path)
        self.step_end("Building photos metadata")

    def add_metadata_to_images(self, folder_path):
        folder_path = Path(folder_path)
        if self.sd is None:
            self.step_start("Loading ParisNeo's fork of AUTOMATIC1111's stable diffusion service")
            self.sd = LollmsSD(self.personality.app, "Album Analyzer")
            self.step_end("Loading ParisNeo's fork of AUTOMATIC1111's stable diffusion service")

        if self.personality_config.save_in_csv_file:
            csv_file = open(folder_path/"metadata.csv","w")
            csv_file.write("file_path,description\n")
        descriptions = "## Descriptions:\n"
        for item in folder_path.glob('**/*'):
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                image = Image.open(item)
                image_stem = item.stem
                image_name = item.name
                image_path = item.resolve()

                self.step_start(f"Understanding the image {image_name}")
                description = self.sd.interrogate(str(image_path)).info
                self.print_prompt("Blip description",description)
                self.step_end(f"Understanding the image {image_name}")
                if self.personality_config.save_in_metadata:
                    # Get existing metadata
                    existing_metadata = image.info.get('exif', b'')

                    # Update existing metadata with new data
                    metadata_dict = {"Image":image_name,"description":description}
                    new_metadata = "\0".join([f"{tag}={value}\0" for tag, value in metadata_dict.items()]).encode("utf8")
                    existing_metadata += new_metadata
                    
                    # Save the modified image
                    image.save(item, exif=existing_metadata)
                    image.close()
                if self.personality_config.save_in_separate_text_file:
                    with open(folder_path/(image_stem+".txt"),"w") as f:
                        f.write(f"Image name: {image_path}\nImage description: {description}\n")
                if self.personality_config.save_in_csv_file:
                    csv_file.write(f"{image_path},{description}\n")
                    csv_file.flush()

                descriptions += f"**{image_name}**: {description}\n\n"
                self.full(descriptions)

        if self.personality_config.save_in_csv_file:
            csv_file.close()
            
    def start(self, prompt="", full_context=""):
        self.new_message("")
        self.process_images()


    
    def add_file(self, path, callback=None):
        """
        Here we implement the file reception handling
        """
        super().add_file(path, callback)

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
        if self.personality_config.album_folder_path!="":
            ASCIIColors.info("Generating")
            self.callback = callback
            self.step_start("Understanding request")
            if self.yes_no("Is the user asking for starting the generation", previous_discussion_text):
                self.step_end("Understanding request")
                self.process_images()
            else:
                self.step_end("Understanding request")
                self.fast_gen(previous_discussion_text, callback=self.callback)
        else:
            self.step_end("Understanding request")
            self.fast_gen(previous_discussion_text, callback=self.callback)
        return ""

