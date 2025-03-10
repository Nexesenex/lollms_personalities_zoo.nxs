import subprocess
from pathlib import Path
from lollms.helpers import ASCIIColors
from lollms.config import TypedConfig, BaseConfig, ConfigTemplate
from lollms.types import MSG_OPERATION_TYPE
from lollms.personality import APScript, AIPersonality
from lollms.utilities import PromptReshaper, discussion_path_to_url
from lollms.functions.prompting.image_gen_prompts import get_image_gen_prompt, get_random_image_gen_prompt
import re
import webbrowser
from typing import Dict, Any, Callable
from pathlib import Path
from PIL import Image
from lollms.client_session import Client
from lollms.prompting import LollmsContextDetails


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
        # Get the current directory
        root_dir = personality.lollms_paths.personal_path
        # We put this in the shared folder in order as this can be used by other personalities.
        shared_folder = root_dir/"shared"
        self.sd_folder = shared_folder / "auto_sd"
        
        
        self.callback = None
        self.tti = None

        self.sd_models_folder = self.sd_folder/"models"/"Stable-diffusion"
        if self.sd_models_folder.exists():
            self.sd_models = [f.stem for f in self.sd_models_folder.iterdir()]
        else:
            self.sd_models = ["Not installeed"]

        personality_config_template = ConfigTemplate(
            [
                {"name":"activate_discussion_mode","type":"bool","value":True,"help":f"If active, the AI will not generate an image until you ask it to, it will just talk to you until you ask it to make the graphical output requested"},
                {"name":"examples_extraction_mathod","type":"str","value":"random","options":["random", "rag_based", "None"], "help":"The generation AI has access to a list of examples of prompts that were crafted and fine tuned by a combination of AI and the main dev of the project. You can select which method lpm uses to search  those data, (none, or random or rag based where he searches examples that looks like the persona to build)"},
                {"name":"number_of_examples_to_recover","type":"int","value":3, "help":"How many example should we give the AI"},
                
                {"name":"production_type","type":"str","value":"an artwork", "options":["a photo","an artwork", "a drawing", "a painting", "a hand drawing", "a design", "a presentation asset", "a presentation background", "a game asset", "a game background", "an icon"],"help":"This selects what kind of graphics the AI is supposed to produce"},
                {"name":"sd_model_name","type":"str","value":self.sd_models[0], "options":self.sd_models, "help":"Name of the model to be loaded for stable diffusion generation"},
                {"name":"sd_address","type":"str","value":"http://127.0.0.1:7860","help":"The address to stable diffusion service"},
                {"name":"sampler_name","type":"str","value":"DPM++ 3M SDE", "options":["Euler a","Euler","LMS","Heun","DPM2","DPM2 a","DPM++ 2S a","DPM++ 2M","DPM++ SDE","DPM++ 2M SDE", "DPM fast", "DPM adaptive", "DPM Karras", "DPM2 Karras", "DPM2 a Karras","DPM++ 2S a Karras","DPM++ 2M Karras","DPM++ SDE Karras","DPM++ 2M SDE Karras" ,"DDIM", "PLMS", "UniPC", "DPM++ 3M SDE", "DPM++ 3M SDE Karras", "DPM++ 3M SDE Exponential"], "help":"Select the sampler to be used for the diffusion operation. Supported samplers ddim, dpms, plms"},                
                {"name":"steps","type":"int","value":40, "min":10, "max":1024},
                {"name":"scale","type":"float","value":5, "min":0.1, "max":100.0},

                {"name":"imagine","type":"bool","value":True,"help":"Imagine the images"},
                {"name":"build_title","type":"bool","value":True,"help":"Build a title for the artwork"},
                {"name":"paint","type":"bool","value":True,"help":"Paint the images"},
                {"name":"use_fixed_negative_prompts","type":"bool","value":True,"help":"Uses parisNeo's preferred negative prompts"},
                {"name":"fixed_negative_prompts","type":"str","value":"(((ugly))), (((duplicate))), ((morbid)), ((mutilated)), out of frame, extra fingers, mutated hands, ((poorly drawn hands)), ((poorly drawn face)), (((mutation))), (((deformed))), blurry, ((bad anatomy)), (((bad proportions))), ((extra limbs)), cloned face, (((disfigured))), ((extra arms)), (((extra legs))), mutated hands, (fused fingers), (too many fingers), (((long neck))), ((watermark)), ((robot eyes))","help":"which negative prompt to use in case use_fixed_negative_prompts is checked"},                
                {"name":"show_infos","type":"bool","value":True,"help":"Shows generation informations"},
                {"name":"continuous_discussion","type":"bool","value":True,"help":"If true then previous prompts and infos are taken into acount to generate the next image"},
                {"name":"automatic_resolution_selection","type":"bool","value":False,"help":"If true then artbot chooses the resolution of the image to generate"},
                {"name":"add_style","type":"bool","value":False,"help":"If true then artbot will choose and add a specific style to the prompt"},
                
                
                {"name":"continue_from_last_image","type":"bool","value":False,"help":"Uses last image as input for next generation"},
                {"name":"img2img_denoising_strength","type":"float","value":7.5, "min":0.01, "max":1.0, "help":"The image to image denoising strength"},
                {"name":"restore_faces","type":"bool","value":True,"help":"Restore faces"},
                {"name":"caption_received_files","type":"bool","value":False,"help":"If active, the received file will be captioned"},

                {"name":"width","type":"int","value":1024, "min":64, "max":4096},
                {"name":"height","type":"int","value":1024, "min":64, "max":4096},

                {"name":"thumbneil_ratio","type":"int","value":2, "min":1, "max":5},

                {"name":"automatic_image_size","type":"bool","value":False,"help":"If true, artbot will select the image resolution"},
                {"name":"skip_grid","type":"bool","value":True,"help":"Skip building a grid of generated images"},
                {"name":"batch_size","type":"int","value":1, "min":1, "max":100,"help":"Number of images per batch (requires more memory)"},
                {"name":"num_images","type":"int","value":1, "min":1, "max":100,"help":"Number of batch of images to generate (to speed up put a batch of n and a single num images, to save vram, put a batch of 1 and num_img of n)"},
                {"name":"seed","type":"int","value":-1},
                {"name":"max_generation_prompt_size","type":"int","value":512, "min":10, "max":personality.config["ctx_size"]},
   
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
                                        "new_image":self.new_image,
                                        "regenerate":self.regenerate,
                                        "show_settings":self.show_settings,
                                    },
                                    "default": self.main_process
                                },                           
                            ],
                            callback=callback
                        )
        self.width=int(self.personality_config.width)
        self.height=int(self.personality_config.height)

    def get_css(self):
        return '<link rel="stylesheet" href="/personalities/art/artbot/assets/tailwind.css">'


    def make_selectable_photo(self, image_id, image_source, client_id, image_infos={}):
        with(open(Path(__file__).parent.parent/"assets/photo.html","r") as f):
            str_data = f.read()
        
        reshaper = PromptReshaper(str_data)
        str_data = reshaper.replace({
            "{{image_id}}":f"{image_id}",
            "{{thumbneil_width}}":f"{self.personality_config.width/self.personality_config.thumbneil_ratio}",
            "{{thumbneil_height}}":f"{self.personality_config.height/self.personality_config.thumbneil_ratio}",
            "{{image_source}}":image_source,
            "{{client_id}}":client_id,
            "{{__infos__}}":str(image_infos).replace("True","true").replace("False","false").replace("None","null")
        })
        return str_data
    def make_selectable_photos(self, html:str):
        with(open(Path(__file__).parent.parent/"assets/photos_galery.html","r") as f):
            str_data = f.read()
        
        reshaper = PromptReshaper(str_data)
        str_data = reshaper.replace({
            "{{photos}}":html
        })
        return str_data
    def print_prompt(self, title, prompt):
        ASCIIColors.red("*-*-*-*-*-*-*-* ", end="")
        ASCIIColors.red(title, end="")
        ASCIIColors.red(" *-*-*-*-*-*-*-*")
        ASCIIColors.yellow(prompt)
        ASCIIColors.red(" *-*-*-*-*-*-*-*")

    def install(self):
        super().install()        
        requirements_file = self.personality.personality_package_path / "requirements.txt"
        # Install dependencies using pip from requirements.txt
        subprocess.run(["pip", "install", "--upgrade", "-r", str(requirements_file)])      

    def remove_image_links(self, markdown_text):
        # Regular expression pattern to match image links in Markdown
        image_link_pattern = r"!\[.*?\]\((.*?)\)"

        # Remove image links from the Markdown text
        text_without_image_links = re.sub(image_link_pattern, "", markdown_text)

        return text_without_image_links


    def help(self, prompt="", full_context="", client:Client=None):
        self.personality.InfoMessage(self.personality.help)
    
    def new_image(self, prompt="", full_context="", client:Client=None):
        self.personality.image_files=[]
        self.personality.info("Starting fresh :)")
        
        
    def show_settings(self, prompt="", full_context="", client:Client=None):
        self.prepare()
        webbrowser.open(self.personality_config.sd_address+"/?__theme=dark")        
        self.set_message_content("Showing Stable diffusion settings UI")
        
    def show_last_image(self, prompt="", full_context=""):
        self.prepare()
        if len(self.personality.image_files)>0:
            self.set_message_content(f"![]({self.personality.image_files})")        
        else:
            self.set_message_content("Showing Stable diffusion settings UI")        
        
    def add_file(self, path, client:Client, callback=None):
        self.new_message("")
        pth = str(path).replace("\\","/").split('/')
        idx = pth.index("uploads")
        pth = "/".join(pth[idx:])

        output = f"## Image:\n![]({pth})\n\n"
        self.set_message_content(output)
        if callback is None and self.callback is not None:
            callback = self.callback

        self.prepare()
        super().add_file(path, client)
        self.personality.image_files.append(path)
        if self.personality_config.caption_received_files:
            self.new_message("", MSG_OPERATION_TYPE.MSG_OPERATION_TYPE_ADD_CHUNK, callback=callback)
            self.step_start("Understanding the image", callback=callback)
            img = Image.open(str(path))
            # Convert the image to RGB mode
            img = img.convert("RGB")
            description = self.personality.model.interrogate_blip([img])[0]
            # description = self.tti.interrogate(str(path)).info
            self.print_prompt("Blip description",description)
            self.step_end("Understanding the image", callback=callback)           
            file_html = self.make_selectable_photo(path.stem,f"/{pth}", client.client_id, {"name":path.stem,"type":"Imported image", "prompt":description})
            output += f"##  Image description :\n{description}\n"
            self.set_message_content(output, callback=callback)
            photos_ui = self.make_selectable_photos(file_html)
            self.set_message_html(photos_ui)
            self.finished_message()
        else:    
            self.set_message_content(f"File added successfully\n", callback=callback)
        
    def regenerate(self, prompt="", full_context="", client:Client=None):
        metadata = client.discussion.get_metadata()
        self.prepare()
        if metadata["positive_prompt"]:
            self.new_message("Regenerating using the previous prompt",MSG_OPERATION_TYPE.MSG_OPERATION_TYPE_STEP_START)
            output0 = f"### Positive prompt:\n{metadata['positive_prompt']}\n\n### Negative prompt:\n{metadata['negative_prompt']}"
            output = output0
            self.set_message_content(output)

            infos = self.paint(metadata["positive_prompt"], metadata["negative_prompt"], metadata["sd_title"], output, client)
         
            self.step_end("Regenerating using the previous prompt")
        else:
            self.set_message_content("Please generate an image first then retry")

    

    def get_styles(self, prompt, full_context, client:Client= None):
        self.step_start("Selecting style")
        styles=[
            "Oil painting",
            "Octane rendering",
            "Cinematic",
            "Art deco",
            "Enameled",
            "Etching",
            "Arabesque",
            "Cross Hatching",
            "Callegraphy",
            "Vector art",
            "Vexel art",
            "Cartoonish",
            "Cubism",
            "Surrealism",
            "Pop art",
            "Pop surrealism",
            "Roschach Inkblot",
            "Flat icon",
            "Material Design Icon",
            "Skeuomorphic Icon",
            "Glyph Icon",
            "Outline Icon",
            "Gradient Icon",
            "Neumorphic Icon",
            "Vintage Icon",
            "Abstract Icon"

        ]
        stl=", ".join(styles)
        prompt=f"{full_context}{self.config.separator_template}{self.config.start_header_id_template}user{self.config.end_header_id_template}{prompt}\nSelect what style(s) among those is more suitable for this {self.personality_config.production_type.split()[-1]}: {stl}\n{self.config.start_header_id_template}assistant{self.config.end_header_id_template}I select"
        stl = self.generate(prompt, self.personality_config.max_generation_prompt_size).strip().replace("</s>","").replace("<s>","")
        self.step_end("Selecting style")

        selected_style = ",".join([s for s in styles if s.lower() in stl])
        return selected_style

    def get_resolution(self, prompt, full_context, default_resolution=[512,512]):

        def extract_resolution(text, default_resolution=[512, 512]):
            # Define a regular expression pattern to match the (w, h) format
            pattern = r'\((\d+),\s*(\d+)\)'
            
            # Search for the pattern in the text
            match = re.search(pattern, text)
            
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                return width, height
            else:
                return default_resolution
                    
        self.step_start("Choosing resolution")
        prompt=f"{full_context}{self.config.separator_template}{self.config.start_header_id_template}user{self.config.end_header_id_template}{prompt}\nSelect a suitable image size (width, height).\nThe default resolution uis ({default_resolution[0]},{default_resolution[1]}){self.config.separator_template}{self.config.start_header_id_template}selected_image_size:"
        sz = self.generate(prompt, self.personality_config.max_generation_prompt_size).strip().replace("</s>","").replace("<s>","").split("\n")[0]

        self.step_end("Choosing resolution")

        return extract_resolution(sz, default_resolution)

    def paint(self, positive_prompt, negative_prompt, sd_title, metadata_infos, client:Client):
        files = []
        ui=""
        metadata_infos0=metadata_infos
        for img in range(self.personality_config.num_images):
            self.step_start(f"Generating image {img+1}/{self.personality_config.num_images}")
            if len(self.personality.image_files)>0:
                file, infos = self.personality.app.tti.paint_from_images(
                                    positive_prompt,
                                    negative_prompt,
                                    self.personality.image_files,
                                    self.personality_config.sampler_name,
                                    self.personality_config.seed,
                                    self.personality_config.scale,
                                    self.personality_config.steps,
                                    self.personality_config.img2img_denoising_strength,
                                    width = self.personality_config.width,
                                    height = self.personality_config.height,
                                    output_path=client.discussion.discussion_folder
                                    
                                )
            else:
                file, infos = self.personality.app.tti.paint(
                                    positive_prompt,
                                    negative_prompt,
                                    self.personality_config.sampler_name,
                                    self.personality_config.seed,
                                    self.personality_config.scale,
                                    self.personality_config.steps,
                                    self.personality_config.img2img_denoising_strength,
                                    width = self.personality_config.width,
                                    height = self.personality_config.height,
                                    output_path=client.discussion.discussion_folder
                                    
                                )
            file = str(file)
            if file!="":
                escaped_url =  discussion_path_to_url(file)
                metadata_infos += f'\n![]({escaped_url})'
                file_html = self.make_selectable_photo(Path(file).stem, escaped_url,client.client_id, infos)
                ui += file_html
                self.set_message_content(metadata_infos) 

        photos_ui = self.make_selectable_photos(self.make_selectable_photos(ui))
        self.set_message_html(photos_ui)

        return infos
    
    def prepare(self):
        if self.personality.app.tti is None:
            self.set_message_content("Lollms can no longer run without setting tti service in lollms settings.\nPlease go to settings page, then in services zoo select a TTI service from the available list.\nYou may need to configure the TTI service if it requires configurations or api key etc...")
            raise Exception("NO TTI service is on")

    def main_process(self, initial_prompt, full_context, context_details:LollmsContextDetails=None, client:Client=None):
        metadata = client.discussion.get_metadata()
        sd_title = metadata.get("sd_title","unnamed")
        metadata_infos=""
        try:
            full_context = context_details.discussion_messages
        except:
            ASCIIColors.warning("Couldn't extract full context portion")    
        if self.personality_config.imagine:
            if self.personality_config.activate_discussion_mode:
                classification = self.multichoice_question("Classify the user prompt.", 
                                                           [
                                                               "The user is making an affirmation",
                                                               "The user is asking a question",
                                                               "The user is requesting to generate, build or make",
                                                               "The user is requesting to modify"
                                                            ], f"{self.config.start_header_id_template}user: "+initial_prompt)

                if classification<=1:
                    prompt = self.build_prompt([
                                    f"{self.config.start_header_id_template}instructions>Artbot is an art generation AI that discusses with humains about art.", #conditionning
                                    f"{self.config.start_header_id_template}discussion:",
                                    full_context,
                                    initial_prompt,
                                    context_details.ai_prefix,
                    ],2)
                    self.print_prompt("Discussion",prompt)

                    response = self.generate(prompt, self.personality_config.max_generation_prompt_size).strip().replace("</s>","").replace("<s>","")
                    self.set_message_content(response)
                    return


            if self.personality_config.automatic_resolution_selection:
                res = self.get_resolution(initial_prompt, full_context, [self.personality_config.width,self.personality_config.height])
                self.width=res[0]
                self.height=res[1]
            else:
                self.width=self.personality_config.width
                self.height=self.personality_config.height

            metadata_infos += f"## Chosen resolution:\n{self.width}x{self.height}"
            self.set_message_content(f"{metadata_infos}")     
            # ====================================================================================
            if self.personality_config.add_style:
                styles = self.get_styles(initial_prompt,full_context)
                metadata_infos += f"## Chosen style: {styles}"
                self.set_message_content(f"{metadata_infos}")     
            else:
                styles = None
            stl = f"{self.system_custom_header('style_choice')} {styles}\n" if styles is not None else ""
            self.step_start("Imagining positive prompt")
            # 1 first ask the model to formulate a query
            past = self.remove_image_links(full_context)

            examples = ""
            expmls = []
            if self.personality_config.examples_extraction_mathod=="random":
                expmls = get_random_image_gen_prompt(self.personality_config.number_of_examples_to_recover)
            elif self.personality_config.examples_extraction_mathod=="rag_based":
                expmls = get_image_gen_prompt(prompt, self.personality_config.number_of_examples_to_recover)
                
            for i,expml in enumerate(expmls):
                examples += f"example {i}:"+expml+"\n"

            prompt = self.build_prompt([
                            self.system_full_header,
                            f"Act as artbot, the art prompt generation AI.",
                            "Use the discussion information to come up with an image generation prompt without referring to it.",
                            f"Be precise and describe the style as well as the {self.personality_config.production_type.split()[-1]} description details.", #conditionning
                            "Do not explain the prompt, just answer with the prompt in the right prompting style.",
                            self.system_custom_header("discussion"),
                            past if self.personality_config.continuous_discussion else '',
                            stl.strip(),
                            self.system_custom_header("Production type") + f"{self.personality_config.production_type}",
                            self.system_custom_header("Instruction") + f"Use the following as examples and follow their format to build the special prompt." if examples!="" else "",
                            self.system_custom_header("Prompt examples") if examples!="" else "",
                            self.system_custom_header("Examples") + f"{examples}",
                            self.system_custom_header("Prompt"),
            ],2)
            


            self.print_prompt("Positive prompt",prompt)

            positive_prompt = self.generate(prompt, self.personality_config.max_generation_prompt_size, callback=self.sink).strip().replace("</s>","").replace("<s>","")
            self.step_end("Imagining positive prompt")
            metadata_infos += f"\n### Positive prompt:\n{positive_prompt}"
            self.set_message_content(f"{metadata_infos}")     
            # ====================================================================================
            # ====================================================================================
            if not self.personality_config.use_fixed_negative_prompts:
                self.step_start("Imagining negative prompt")
                # 1 first ask the model to formulate a query
                prompt = self.build_prompt([
                                self.system_full_header +"Act as artbot, the art prompt generation AI. Use the previous discussion information to come up with a negative generation prompt.", #conditionning
                                "The negative prompt is a list of keywords that should not be present in our image.",
                                "Try to force the generator not to generate text or extra fingers or deformed faces.",
                                "Use as many words as you need depending on the context.",
                                "To give more importance to a term put it ibti multiple brackets ().",
                                self.system_custom_header("discussion"),
                                past if self.personality_config.continuous_discussion else '',
                                stl,
                                self.system_custom_header("positive prompt") + f"{positive_prompt}",
                                self.system_custom_header("negative prompt")
                ],6)

                self.print_prompt("Generate negative prompt", prompt)
                negative_prompt = "((morbid)),"+self.generate(prompt, self.personality_config.max_generation_prompt_size).strip().replace("</s>","").replace("<s>","")
                self.step_end("Imagining negative prompt")
            else:
                negative_prompt = self.personality_config.fixed_negative_prompts
            metadata_infos += f"\n### Negative prompt:\n{negative_prompt}"
            self.set_message_content(f"{metadata_infos}")     
            # ====================================================================================            
            if self.personality_config.build_title:
                self.step_start("Making up a title")
                prompt = self.build_prompt([
                    self.system_full_header,
                    "Given this image description prompt and negative prompt, make a consize title",
                    self.system_custom_header("positive_prompt"),
                    positive_prompt,
                    self.system_custom_header("negative_prompt"),
                    negative_prompt,
                    self.system_custom_header("title")
                ])

                self.print_prompt("Make up a title", prompt)
                sd_title = self.generate_text(prompt, max_size= self.personality_config.max_generation_prompt_size)
                if sd_title:
                    sd_title = sd_title.strip().replace("</s>","").replace("<s>","")
                self.step_end("Making up a title")
                metadata_infos += f"{sd_title}"
                self.set_message_content(f"{metadata_infos}")
                
        else:
            self.width=self.personality_config.width
            self.height=self.personality_config.height
            prompt = initial_prompt.split("\n")
            if len(prompt)>1:
                positive_prompt = prompt[0]
                negative_prompt = prompt[1]
            else:
                positive_prompt = prompt[0]
                negative_prompt = ""

        metadata["positive_prompt"]=positive_prompt
        metadata["negative_prompt"]=negative_prompt
        metadata["sd_title"]=sd_title
        client.discussion.set_metadata(metadata)
        output = metadata_infos

        if self.personality_config.paint:
            self.prepare()
            infos = self.paint(positive_prompt, negative_prompt, sd_title, metadata_infos, client)
            self.set_message_content(output.strip())

        else:
            infos = None
        if self.personality_config.show_infos and infos:
            self.json("infos", infos)

    async def handle_request(self, data: dict, client:Client=None) -> Dict[str, Any]:
        """
        Handle client requests.

        Args:
            data (dict): A dictionary containing the request data.
            client (Client): A refertence to the client asking for this request.

        Returns:
            dict: A dictionary containing the response, including at least a "status" key.

        This method should be implemented by a class that inherits from this one.

        Example usage:
        ```
        handler = YourHandlerClass()
        client = checkaccess(lollmsServer, client_id)
        request_data = {"command": "some_command", "parameters": {...}}
        response = handler.handle_request(request_data, client)
        ```
        """
        metadata = client.discussion.get_metadata()

        operation = data.get("name","variate")
        prompt = data.get("prompt","")
        negative_prompt =  data.get("negative_prompt","")
        if operation=="variate":
            imagePath = data.get("imagePath","")
            ASCIIColors.info(f"Regeneration requested for file : {imagePath}")
            self.new_image()
            ASCIIColors.info("Building new image")
            self.personality.image_files.append(self.personality.lollms_paths.personal_outputs_path/"sd"/imagePath.split("/")[-1])
            self.personality.info("Regenerating")
            metadata["positive_prompt"] = prompt
            metadata["negative_prompt"] = negative_prompt
            self.new_message(f"Generating {self.personality_config.num_images} variations")
            self.prepare()
            self.regenerate()
            
            return {"status":True, "message":"Image is now ready to be used as variation"}
        elif operation=="set_as_current":
            imagePath = data.get("imagePath","")
            ASCIIColors.info(f"Regeneration requested for file : {imagePath}")
            self.new_image()
            ASCIIColors.info("Building new image")
            self.personality.image_files.append(self.personality.lollms_paths.personal_outputs_path/"sd"/imagePath.split("/")[-1])
            ASCIIColors.info("Regenerating")
            return {"status":True, "message":"Image is now set as the current image for image to image operation"}

        return {"status":False, "message":"Unknown operation"}

    def run_workflow(self,  context_details:LollmsContextDetails=None, client:Client=None,  callback: Callable[[str | list | None, MSG_OPERATION_TYPE, str, AIPersonality| None], bool]=None):
        """
        This function generates code based on the given parameters.

        Args:
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
            client_id: The client ID for code generation.
            callback (function, optional): The callback function for code generation.

        Returns:
            None
        """
        prompt = context_details.prompt
        previous_discussion_text = context_details.discussion_messages
        self.callback = callback
        self.main_process(prompt, previous_discussion_text,context_details,client)

        return ""

