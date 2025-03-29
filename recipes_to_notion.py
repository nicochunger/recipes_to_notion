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
    return convert_from_path(pdf_path, dpi=300)


def image_to_base64(image):
    """Convert a PIL Image to a base64-encoded string."""
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def extract_text_from_image(image):
    """Use Gemini 2.0 to extract text from a base64-encoded image."""

    prompt = """Extract the recipe(s) from this image. The content is in Spanish, and your 
    output should preserve the original Spanish language. Do not translate titles, ingredients, 
    or instructions.

    There may be more than one recipe in the image. If so, the one at the top is the main recipe. 
    Additional recipes, sub-recipes (e.g., for sauces, toppings), or variations should be listed 
    under Alternative Recipes, each separated using the format provided below.

    If any ingredient has the quantity "C/N", replace it with "a gusto".

    Use the following exact format for your response:
    
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
    return response.text


def parse_recipe_text(text):
    """Parse the recipe text into main recipe and alternative recipes."""
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
    (
        main_emoji,
        main_title,
        main_portions,
        main_vegetarian,
        main_ingredients,
        main_instructions,
        main_notes,
    ) = main_recipe

    # Create the children blocks list starting with the main recipe
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Ingredientes"}}]
            },
        }
    ]

    # Add ingredients
    for ingredient in main_ingredients:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": ingredient}}]
                },
            }
        )

    # Add instructions
    children.append(
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Preparación"}}]
            },
        }
    )

    for instruction in main_instructions:
        children.append(
            {
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": instruction}}]
                },
            }
        )

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
                    },
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "Ingredientes"}}
                            ]
                        },
                    },
                ]
            )

            for ingredient in alt_ingredients:
                children.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [
                                {"type": "text", "text": {"content": ingredient}}
                            ]
                        },
                    }
                )

            children.extend(
                [
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "Preparación"}}
                            ]
                        },
                    }
                ]
            )

            for instruction in alt_instructions:
                children.append(
                    {
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [
                                {"type": "text", "text": {"content": instruction}}
                            ]
                        },
                    }
                )

            # Add notes for alternative recipe if they exist
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
            },
            children=children,
        )
        return 200, new_page
    except Exception as e:
        return 400, str(e)


def main(pdf_path):
    # Verify the PDF file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images = pdf_to_images(pdf_path)
    full_text = ""
    for image in images:
        text = extract_text_from_image(image)
        full_text += text + "\n"

    print(full_text)

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

    status_code, response = create_notion_page(main_recipe, alternative_recipes)
    if status_code == 200:
        print(f"Recipe '{main_recipe[1]}' successfully uploaded to Notion.")
    else:
        print(f"Failed to upload recipe. Response: {response}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert recipe PDF to Notion page")
    parser.add_argument("pdf_path", help="Path to the recipe PDF file")
    args = parser.parse_args()

    main(args.pdf_path)
