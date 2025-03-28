# Recipes to Notion

A Python script to digitize printed recipe pages and automatically import them into a Notion database. Originally created to digitize a collection of printed recipes from a cooking class.

## How it Works

1. Takes scanned PDF pages of recipes as input
2. Converts PDF pages to high-quality images
3. Uses Google's Gemini AI to extract recipe text and structure from the images
4. Automatically creates organized recipe pages in a Notion database

## Prerequisites

- Python 3.x
- A Google Cloud account with Gemini API access
- A Notion account with API integration
- Scanned recipes in PDF format

## Setup

1. Install required packages:
   ```bash
   pip install pillow requests python-dotenv google-generativeai pdf2image
   ```

2. Create a `.env` file with your API credentials:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   NOTION_TOKEN=your_notion_token
   NOTION_DATABASE_ID=your_database_id
   ```

3. Ensure you have a Notion database set up with at least a "Title" property

## Usage

1. Update the `pdf_path` variable in the script with the path to your recipe PDF
2. Run the script:
   ```bash
   python recipes_to_notion.py
   ```

The script will process each page of the PDF and create structured recipe pages in your Notion database with:
- Recipe title
- Ingredient list
- Step-by-step instructions

## Notes

- The script uses a 300 DPI setting for optimal text recognition
- Make sure your scanned documents are clear and legible
- Each recipe should be clearly formatted with a title, ingredients, and instructions
