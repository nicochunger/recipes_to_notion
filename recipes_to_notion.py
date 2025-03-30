import argparse
import base64
import os
from typing import List, Optional

from dotenv import load_dotenv
from google import genai  # Revert to using Google's Gemini API
from notion_client import Client
from pdf2image import convert_from_path
from pydantic import BaseModel

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Set up models to be used
# TEXT_MODEL = "gemini-2.5-pro-exp-03-25"  # Model for text generation
TEXT_MODEL = "gemini-2.0-flash"  # Model for text generation
IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"  # Model for image generation

# Configure clients
genai_client = genai.Client(api_key=GEMINI_API_KEY)  # Revert to Google Gemini client
notion = Client(auth=NOTION_TOKEN)


# Define the Schema for the recipes
class Recipe(BaseModel):
    emoji: Optional[str]  # Made optional
    title: str
    portions: Optional[int]
    vegetarian: Optional[bool]  # Made optional
    ingredients: List[str]
    instructions: List[str]
    notes: Optional[List[str]]  # Made optional


class RecipeExtractionResponse(BaseModel):
    main_recipe: Recipe
    alternative_recipes: Optional[List[Recipe]]  # Made optional


def pdf_to_images(pdf_path):
    """Convert PDF pages to images."""
    print(f"Converting PDF '{pdf_path}' to images...")
    return convert_from_path(pdf_path, dpi=300)


def image_to_base64(image):
    """Convert a PIL Image to a base64-encoded string."""
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def gemini_call(model, contents, config=None):
    """Call the Gemini API to generate content."""
    response = genai_client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return response


def extract_text_from_image(image):
    """Use Gemini to extract text from an image."""
    print("Extracting text from image using Gemini API...")

    prompt = """Extract the recipe(s) from this image. The content is in Spanish, and your 
    output should preserve the original Spanish language. Do not translate titles, ingredients, 
    or instructions.

    There may be more than one recipe in the image. If so, the one at the top is the main recipe. 
    Additional recipes, sub-recipes (e.g., for sauces, toppings), or variations should be listed 
    under Alternative Recipes, each separated using the format provided below.

    If any ingredient has the quantity "C/N", replace it with "a gusto".

    Make sure to include an actual emoji that represents the recipe.

    Ensure that the output is valid JSON and exactly follows the provided schema.
    """

    # Call the Gemini API to generate content
    response = gemini_call(
        model=TEXT_MODEL,
        contents=[prompt, image],
        config={
            "response_mime_type": "application/json",
            "response_schema": RecipeExtractionResponse,
        },
    )

    # The returned response will be a JSON string, but you can also use the parsed Pydantic model.
    structured_recipes: RecipeExtractionResponse = response.parsed
    print("Recipe extraction completed.")

    return structured_recipes


def parse_recipe_text(response: RecipeExtractionResponse):
    """Parse the structured JSON response into main recipe and alternative recipes."""
    print("Parsing structured recipe data...")

    # Extract main recipe
    main_recipe = (
        response.main_recipe.emoji or "🍽️",  # Default emoji if missing
        response.main_recipe.title,
        response.main_recipe.portions,
        response.main_recipe.vegetarian or False,  # Default to False if missing
        response.main_recipe.ingredients,
        response.main_recipe.instructions,
        response.main_recipe.notes or [],  # Default to empty list if missing
    )

    print(f"Main recipe: {response.main_recipe.title}")

    # Extract alternative recipes
    alternative_recipes = [
        (
            alt_recipe.emoji or "🍽️",  # Default emoji if missing
            alt_recipe.title,
            alt_recipe.portions,
            alt_recipe.vegetarian or False,  # Default to False if missing
            alt_recipe.ingredients,
            alt_recipe.instructions,
            alt_recipe.notes or [],  # Default to empty list if missing
        )
        for alt_recipe in (
            response.alternative_recipes or []
        )  # Handle missing alternatives
    ]

    print("Parsing completed.")
    return main_recipe, alternative_recipes


def create_notion_page(main_recipe, alternative_recipes):
    """Create a new page in Notion with main recipe and alternatives."""
    print(f"Creating Notion page for recipe: {main_recipe[1]}...")
    (
        main_emoji,
        main_title,
        main_portions,
        main_vegetarian,
        main_ingredients,
        main_instructions,
        main_notes,
    ) = main_recipe

    # Build the main recipe columns using correct nested structure
    children = [
        {
            "object": "block",
            "type": "column_list",
            "column_list": {
                "children": [  # Columns go inside this children property
                    {
                        "object": "block",
                        "type": "column",
                        "column": {
                            "children": [
                                {
                                    "object": "block",
                                    "type": "heading_2",
                                    "heading_2": {
                                        "rich_text": [
                                            {
                                                "type": "text",
                                                "text": {"content": "Ingredientes"},
                                            }
                                        ]
                                    },
                                },
                                *[
                                    {
                                        "object": "block",
                                        "type": "bulleted_list_item",
                                        "bulleted_list_item": {
                                            "rich_text": [
                                                {
                                                    "type": "text",
                                                    "text": {"content": ingredient},
                                                }
                                            ]
                                        },
                                    }
                                    for ingredient in main_ingredients
                                ],
                            ]
                        },
                    },
                    {
                        "object": "block",
                        "type": "column",
                        "column": {
                            "children": [
                                {
                                    "object": "block",
                                    "type": "heading_2",
                                    "heading_2": {
                                        "rich_text": [
                                            {
                                                "type": "text",
                                                "text": {"content": "Preparación"},
                                            }
                                        ]
                                    },
                                },
                                *[
                                    {
                                        "object": "block",
                                        "type": "numbered_list_item",
                                        "numbered_list_item": {
                                            "rich_text": [
                                                {
                                                    "type": "text",
                                                    "text": {"content": instruction},
                                                }
                                            ]
                                        },
                                    }
                                    for instruction in main_instructions
                                ],
                            ]
                        },
                    },
                ]
            },
        }
    ]

    # Add notes if they exist
    if main_notes:
        children.extend(
            [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Notas"}}]
                    },
                }
            ]
        )

        for note in main_notes:
            children.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": note}}]
                    },
                }
            )

    # Add alternative recipes if they exist
    if alternative_recipes:
        children.extend(
            [
                {"object": "block", "type": "divider", "divider": {}},
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": "Recetas Alternativas"},
                            }
                        ]
                    },
                },
            ]
        )
        for (
            alt_emoji,
            alt_title,
            alt_portions,
            alt_vegetarian,
            alt_ingredients,
            alt_instructions,
            alt_notes,
        ) in alternative_recipes:
            # Add alternative recipe title
            children.extend(
                [
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [
                                {"type": "text", "text": {"content": alt_title}}
                            ]
                        },
                    }
                ]
            )
            # Build two columns for alternative recipe ingredients and instructions
            children.append(
                {
                    "object": "block",
                    "type": "column_list",
                    "column_list": {
                        "children": [
                            {
                                "object": "block",
                                "type": "column",
                                "column": {
                                    "children": [
                                        {
                                            "object": "block",
                                            "type": "heading_2",
                                            "heading_2": {
                                                "rich_text": [
                                                    {
                                                        "type": "text",
                                                        "text": {
                                                            "content": "Ingredientes"
                                                        },
                                                    }
                                                ]
                                            },
                                        },
                                        *[
                                            {
                                                "object": "block",
                                                "type": "bulleted_list_item",
                                                "bulleted_list_item": {
                                                    "rich_text": [
                                                        {
                                                            "type": "text",
                                                            "text": {
                                                                "content": ingredient
                                                            },
                                                        }
                                                    ]
                                                },
                                            }
                                            for ingredient in alt_ingredients
                                        ],
                                    ]
                                },
                            },
                            {
                                "object": "block",
                                "type": "column",
                                "column": {
                                    "children": [
                                        {
                                            "object": "block",
                                            "type": "heading_2",
                                            "heading_2": {
                                                "rich_text": [
                                                    {
                                                        "type": "text",
                                                        "text": {
                                                            "content": "Preparación"
                                                        },
                                                    }
                                                ]
                                            },
                                        },
                                        *[
                                            {
                                                "object": "block",
                                                "type": "numbered_list_item",
                                                "numbered_list_item": {
                                                    "rich_text": [
                                                        {
                                                            "type": "text",
                                                            "text": {
                                                                "content": instruction
                                                            },
                                                        }
                                                    ]
                                                },
                                            }
                                            for instruction in alt_instructions
                                        ],
                                    ]
                                },
                            },
                        ]
                    },
                }
            )
            # Add alternative recipe notes if they exist
            if alt_notes:
                children.extend(
                    [
                        {
                            "object": "block",
                            "type": "heading_3",
                            "heading_3": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": "Notas"}}
                                ]
                            },
                        }
                    ]
                )
                for note in alt_notes:
                    children.append(
                        {
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": note}}
                                ]
                            },
                        }
                    )
            children.append({"object": "block", "type": "divider", "divider": {}})

    # Create the page with properties and icon
    try:
        new_page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            icon={"type": "emoji", "emoji": main_emoji} if main_emoji else None,
            properties={
                "Nombre": {"title": [{"text": {"content": main_title}}]},
                "Porciones": {"number": main_portions if main_portions else 0},
                "Vegetariano": {"checkbox": main_vegetarian},
                "Tags": {"multi_select": [{"name": "IAG"}]},
            },
            children=children,
        )
        print(f"Notion page for '{main_recipe[1]}' created successfully.")
        return 200, new_page
    except Exception as e:
        print(f"Failed to create Notion page for '{main_recipe[1]}': {e}")
        return 400, str(e)


def generate_recipe_image(recipe_title, recipe_text):
    """Generate an image using Gemini 2.0 Flash Experimental."""
    print(f"Generating image for recipe: {recipe_title}...")
    import re
    from io import BytesIO

    from google.genai import types
    from PIL import Image

    # Step 1: Generate the image generation prompt
    print("Generating detailed image generation prompt...")
    prompt_for_prompt = f"""
    I want you to write out a prompt for an LLM that creates images. Again you will just write the 
    prompt itself. I have a base prompt, but you should fill it out with details about the dish. 
    This is the base prompt:

    A wide-format, highly detailed, ultra-photorealistic image of a freshly prepared dish
    placed prominently in the center of a rustic wooden table. The dish is the clear focus,
    beautifully lit with soft natural light that enhances its color and texture. Surrounding
    it, in the background or off to the side, a few of the raw ingredients used in the recipe
    are arranged casually. The atmosphere is warm and natural, evoking the feeling of a cozy,
    artisanal kitchen.

    Now I will give you a recipe of the dish and you modify and complete this prompt according to this 
    recipe. Make sure that it's faithful to the recipe and how the final dish would look like according 
    to how it's prepared. If the recipe has alternative dishes, use common sense to determine which 
    one to focus on and if any of the alternative ones are side dishes to be included. Here is the recipe:

    {recipe_text}
    """
    # Step 1: Call the Gemini API to generate the detailed prompt
    response_prompt = gemini_call(TEXT_MODEL, prompt_for_prompt)
    detailed_prompt = response_prompt.text.strip()
    print("Detailed image generation prompt created.")

    # Step 2: Generate the image using Gemini 2.0 Flash Experimental
    print("Generating image using Gemini 2.0 Flash Experimental...")
    response_image = gemini_call(
        IMAGE_MODEL,
        contents=detailed_prompt,
        config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
    )
    for part in response_image.candidates[0].content.parts:
        if part.inline_data is not None:
            image = Image.open(BytesIO(part.inline_data.data))
            # Ensure the Images folder exists
            image_dir = os.path.join(os.getcwd(), "Images")
            os.makedirs(image_dir, exist_ok=True)
            # Sanitize recipe title for filename
            safe_title = re.sub(r'[\\/*?:"<>|]', "", recipe_title)
            file_path = os.path.join(image_dir, f"{safe_title}.png")
            image.save(file_path)
            print(f"Image for '{recipe_title}' saved to '{file_path}'.")
            return file_path

    print(f"Failed to generate image for '{recipe_title}'.")
    return None


def process_pdf(pdf_path):
    """Process a single PDF file."""
    print(f"\nProcessing file: {pdf_path}")

    try:
        # Convert PDF to images
        images = pdf_to_images(pdf_path)
        print(f"Converted PDF to {len(images)} image(s).")

        # Extract text from images
        for i, image in enumerate(images, start=1):
            print(f"Processing image {i}/{len(images)}...")
            structured_response = extract_text_from_image(image)

        print("All images processed. Extracted structured response.")

        # Parse the structured response
        main_recipe, alternative_recipes = parse_recipe_text(structured_response)

        # Create Notion page
        status_code, response = create_notion_page(main_recipe, alternative_recipes)
        if status_code == 200:
            print(f"Recipe '{main_recipe[1]}' successfully uploaded to Notion.")
        else:
            print(f"Failed to upload recipe. Response: {response}")

        # Generate and save recipe image
        print("Starting image generation process...")
        generate_recipe_image(main_recipe[1], structured_response.model_dump_json())

    except Exception as e:
        print(f"An error occurred while processing '{pdf_path}': {e}")


def main(input_path):
    """Process a single PDF or all PDFs in a folder."""
    if os.path.isfile(input_path):
        # Process a single PDF file
        print(f"Input is a file: {input_path}")
        process_pdf(input_path)
    elif os.path.isdir(input_path):
        # Process all PDFs in the folder
        print(f"Input is a folder: {input_path}")
        pdf_files = sorted([f for f in os.listdir(input_path) if f.endswith(".pdf")])
        if not pdf_files:
            print(f"No PDF files found in folder '{input_path}'.")
            return

        print(
            f"Found {len(pdf_files)} PDF file(s) in folder '{input_path}': {pdf_files}"
        )
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_path, pdf_file)
            process_pdf(pdf_path)
    else:
        print(f"Invalid input: '{input_path}' is neither a file nor a folder.")
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert recipe PDFs to Notion pages")
    parser.add_argument(
        "input_path", help="Path to a single PDF file or a folder containing PDF files"
    )
    args = parser.parse_args()

    print("Starting the recipe-to-Notion process...")
    main(args.input_path)
    print("Process completed.")
