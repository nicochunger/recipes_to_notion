import argparse
import base64
import os

from dotenv import load_dotenv
from google import genai  # Revert to using Google's Gemini API
from notion_client import Client
from pdf2image import convert_from_path

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Configure clients
genai_client = genai.Client(api_key=GEMINI_API_KEY)  # Revert to Google Gemini client
notion = Client(auth=NOTION_TOKEN)


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


def extract_text_from_image(image):
    """Use Gemini 2.5 to extract text from an image."""
    print("Extracting text from image using Gemini API...")

    prompt = """Extract the recipe(s) from this image. The content is in Spanish, and your 
    output should preserve the original Spanish language. Do not translate titles, ingredients, 
    or instructions.

    There may be more than one recipe in the image. If so, the one at the top is the main recipe. 
    Additional recipes, sub-recipes (e.g., for sauces, toppings), or variations should be listed 
    under Alternative Recipes, each separated using the format provided below.

    If any ingredient has the quantity "C/N", replace it with "a gusto".

    Use the following exact format for your response. Make sure to include all the sections and 
    their title as "[Section]: [Content]". Here is the recipe:
    
    Emoji: [Choose one appropriate emoji that best represents this recipe]
    Title: [Recipe Title]
    Portions: [number of portions/servings]
    Vegetarian: [yes/no - determine if the recipe is vegetarian based on ingredients]
    Ingredients:
    - [list of ingredients]
    Instructions:
    - [list of instructions. Put each sentence on a new line]
    Notes:
    - [any additional notes that appear handwritten at the bottom]

        Alternative Recipes:
    1.
    Title: [Recipe Title]
    Portions: [number of portions/servings]
    Vegetarian: [yes/no]
    Ingredients:
    - [list of ingredients]
    Instructions:
    - [list of instructions]
    2.
    (same format as before and so on for each recipe)
    """

    # Call the Gemini API to generate content
    response = genai_client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25",
        contents=[prompt, image],
    )
    print("Text extraction completed.")
    return response.text


def parse_recipe_text(text):
    """Parse the recipe text into main recipe and alternative recipes."""
    print("Parsing extracted text into structured recipe data...")
    sections = text.split("Alternative Recipes:")
    main_recipe = sections[0]
    alternative_recipes = []

    def parse_single_recipe(recipe_text):
        lines = recipe_text.split("\n")
        emoji = ""
        title = ""
        portions = None
        vegetarian = False
        ingredients = []
        instructions = []
        notes = []
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("Emoji:"):
                emoji = line.replace("Emoji:", "").strip()
            elif line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
            elif line.startswith("Portions:"):
                try:
                    portions = int(line.replace("Portions:", "").strip().split()[0])
                except:
                    portions = None
            elif line.startswith("Vegetarian:"):
                vegetarian = "yes" in line.lower()
            elif line.startswith("Ingredients:"):
                current_section = "ingredients"
            elif line.startswith("Instructions:"):
                current_section = "instructions"
            elif line.startswith("Notes:"):
                current_section = "notes"
            elif line and line.startswith("-"):
                if current_section == "ingredients":
                    ingredients.append(line[1:].strip())
                elif current_section == "instructions":
                    instructions.append(line[1:].strip())
                elif current_section == "notes":
                    notes.append(line[1:].strip())

        return emoji, title, portions, vegetarian, ingredients, instructions, notes

    (
        main_emoji,
        main_title,
        main_portions,
        main_vegetarian,
        main_ingredients,
        main_instructions,
        main_notes,
    ) = parse_single_recipe(main_recipe)

    if len(sections) > 1:
        alt_recipes_text = sections[1]
        import re

        alt_recipe_sections = re.split(r"\d+\.", alt_recipes_text)
        for section in alt_recipe_sections:
            if section.strip():
                recipe = parse_single_recipe(section)
                if recipe[1]:  # If there's a title
                    alternative_recipes.append(recipe)

    print("Parsing completed.")
    return (
        main_emoji,
        main_title,
        main_portions,
        main_vegetarian,
        main_ingredients,
        main_instructions,
        main_notes,
    ), alternative_recipes


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
    """Generate an image using Gemini 2.5 Pro for prompt generation and Gemini 2.0 Flash Experimental for image generation."""
    print(f"Generating image for recipe: {recipe_title}...")
    import re
    from io import BytesIO

    from google.genai import types
    from PIL import Image

    # Step 1: Generate the image generation prompt using Gemini 2.5 Pro
    print("Generating detailed image generation prompt using Gemini 2.5 Pro...")
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
    response_prompt = genai_client.models.generate_content(
        model="gemini-2.5-pro-exp-03-25",
        contents=prompt_for_prompt,
    )
    detailed_prompt = response_prompt.text.strip()
    print("Detailed image generation prompt created.")

    # Step 2: Generate the image using Gemini 2.0 Flash Experimental
    print("Generating image using Gemini 2.0 Flash Experimental...")
    response_image = genai_client.models.generate_content(
        model="gemini-2.0-flash-exp-image-generation",
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


def main(pdf_path):
    # Verify the PDF file exists
    print(f"Verifying if the file '{pdf_path}' exists...")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    print(f"File '{pdf_path}' found.")

    # Convert PDF to images
    images = pdf_to_images(pdf_path)
    print(f"Converted PDF to {len(images)} image(s).")

    # Extract text from images
    full_text = ""
    for i, image in enumerate(images, start=1):
        print(f"Processing image {i}/{len(images)}...")
        text = extract_text_from_image(image)
        full_text += text + "\n"

    print("All images processed. Extracted text:")
    print(full_text)

    # Parse the extracted text
    main_recipe, alternative_recipes = parse_recipe_text(full_text)
    if not main_recipe[1]:  # Check title instead of index 0 (now emoji)
        main_recipe = (
            "🍽️",  # Default emoji
            "Untitled Recipe",
            None,
            False,
            main_recipe[4],
            main_recipe[5],
            main_recipe[6],
        )

    # Create Notion page
    status_code, response = create_notion_page(main_recipe, alternative_recipes)
    if status_code == 200:
        print(f"Recipe '{main_recipe[1]}' successfully uploaded to Notion.")
    else:
        print(f"Failed to upload recipe. Response: {response}")

    # Generate and save recipe image
    print("Starting image generation process...")
    image_file = generate_recipe_image(main_recipe[1], full_text)
    if image_file:
        print(f"Recipe image saved to {image_file}")
    else:
        print("No recipe image was generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert recipe PDF to Notion page")
    parser.add_argument("pdf_path", help="Path to the recipe PDF file")
    args = parser.parse_args()

    print("Starting the recipe-to-Notion process...")
    main(args.pdf_path)
    print("Process completed.")
