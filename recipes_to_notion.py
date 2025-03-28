import argparse
import os

import requests
from dotenv import load_dotenv
from google import genai

# from google.genai import types
from pdf2image import convert_from_path

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Configure Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)


def pdf_to_images(pdf_path):
    """Convert PDF pages to images."""
    return convert_from_path(pdf_path, dpi=300)


def extract_text_from_image(image):
    """Use Gemini 2.0 to extract text from a PIL Image."""
    prompt = """Extract the recipe from this image and format it as follows:
    Title: [Recipe Title]
    Ingredients:
    - [list of ingredients]
    Instructions:
    - [list of instructions. Put each sentence on a new line]
    Notes:
    - [any additional notes that appear handwritten at the bottom]

    There might be more than one recipe in the image. If so, the one at the top is the main one.
    The others appear below separated by dashed lines. Add these to your response and format them as follows:
    Alternative Recipes:
    1.
    Title: [Recipe Title]
    Ingredients:
    - [list of ingredients]
    Instructions:
    - [list of instructions]
    2.
    (same format as before and so on for each recipe)
    """
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt, image],
    )
    return response.text


def parse_recipe_text(text):
    """Parse the recipe text into title, ingredients, and instructions."""
    sections = text.split("\n")
    title = ""
    ingredients = []
    instructions = []
    notes = []

    current_section = None
    for line in sections:
        line = line.strip()
        if line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
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

    return title, ingredients, instructions


def create_notion_page(recipe_title, ingredients, instructions):
    """Create a new page in the specified Notion database with separate blocks."""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Create bullet list items for ingredients and instructions
    ingredient_items = [{"text": {"content": item}} for item in ingredients]
    instruction_items = [{"text": {"content": item}} for item in instructions]

    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {"Title": {"title": [{"text": {"content": recipe_title}}]}},
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"text": [{"text": {"content": "Ingredients"}}]},
            },
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"text": ingredient_items},
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"text": [{"text": {"content": "Instructions"}}]},
            },
            {
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"text": instruction_items},
            },
        ],
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code, response.json()


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

    title, ingredients, instructions = parse_recipe_text(full_text)
    if not title:
        title = "Untitled Recipe"
    print(f"Title: {title}")
    print("Ingredients:", ingredients)
    print("Instructions:", instructions)

    # status_code, response = create_notion_page(title, ingredients, instructions)
    # if status_code == 200:
    #     print(f"Recipe '{title}' successfully uploaded to Notion.")
    # else:
    #     print(f"Failed to upload recipe. Response: {response}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert recipe PDF to Notion page")
    parser.add_argument("pdf_path", help="Path to the recipe PDF file")
    args = parser.parse_args()

    main(args.pdf_path)
