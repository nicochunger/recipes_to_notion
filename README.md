# Recipes to Notion

A quick personal project to digitize printed recipe pages and automatically import them into a Notion database. 
A few years ago I attended a cooking class and we were given a lot of printed recipes. I also had a Notion database where I store some of my favourite recipes so I figured I could use LLMs to parse these printed recipes and use the Notion API to upload them directly.

## Features

- **PDF to Image Conversion**: Converts scanned PDF pages into high-quality images for processing.
- **AI-Powered Text Extraction**: Uses Google's Gemini AI to extract recipe data, including titles, ingredients, instructions, and notes, directly from images.
- **Structured JSON Parsing**: Extracted data is returned in a structured JSON format, ensuring accuracy and consistency.
- **Notion Integration**: Automatically creates recipe pages in a Notion database with:
  - Recipe title
  - Emoji representation
  - Ingredient list
  - Step-by-step instructions
  - Notes
  - Alternative recipes (if available)
- **Image Generation**: Generates photorealistic images of the recipes using Gemini's image generation capabilities.

## How it Works

1. **Input**: Provide a single PDF file or a folder containing multiple PDFs of scanned recipes.
2. **PDF to Image Conversion**: Each page of the PDF is converted into a high-resolution image.
3. **AI Extraction**: The Gemini AI extracts recipe data from the images, preserving the original language (e.g., Spanish) and formatting.
4. **Structured Parsing**: The extracted data is parsed into a structured format using Pydantic models.
5. **Notion Page Creation**: The script creates a detailed recipe page in your Notion database, including:
   - Main recipe details
   - Alternative recipes (if available)
   - Organized sections for ingredients, instructions, and notes
6. **Image Generation**: A photorealistic image of the recipe is generated and saved locally.

## Prerequisites

- Python 3.x
- A Google Cloud account with Gemini API access
- A Notion account with API integration
- Scanned recipes in PDF format

## Setup

1. **Install Required Packages**:
   ```bash
   pip install pillow requests python-dotenv google-generativeai pdf2image notion-client
   ```

2. **Set Up Environment Variables**:
   Create a `.env` file in the project directory with the following keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   NOTION_TOKEN=your_notion_token
   NOTION_DATABASE_ID=your_database_id
   ```

3. **Prepare Your Notion Database**:
   - Create a database in Notion with the following properties:
     - `Nombre` (Title)
     - `Porciones` (Number)
     - `Vegetariano` (Checkbox)
     - `Tags` (Multi-select)

4. **Ensure PDF Quality**:
   - Use high-quality scans (300 DPI recommended) for better text recognition.
   - Ensure recipes are clearly formatted with titles, ingredients, and instructions.

## Usage

1. **Run the Script**:
   Provide the path to a single PDF file or a folder containing multiple PDFs:
   ```bash
   python recipes_to_notion.py <input_path>
   ```

   Example:
   ```bash
   python recipes_to_notion.py PDFs/
   ```

2. **Output**:
   - The script will process each PDF and create corresponding recipe pages in your Notion database.
   - Generated recipe images will be saved in the `Images` folder in the project directory.

## Notes

- **Language Support**: The script preserves the original language of the recipes (e.g., Spanish) and does not translate titles, ingredients, or instructions.
- **Handling Missing Data**: Default values are used for missing fields (e.g., a default emoji for recipes without one).
- **Alternative Recipes**: If a recipe includes sub-recipes (e.g., sauces or toppings), they are added as alternative recipes in the Notion page.
- **Image Generation**: The generated recipe images are photorealistic and include details about the dish and its ingredients.

## Example Workflow

1. **Input**:
   A scanned PDF containing the following recipe:
   ```
   Título: Ensalada César
   Porciones: 4
   Ingredientes:
   - Lechuga romana
   - Crutones
   - Queso parmesano
   - Aderezo César
   Instrucciones:
   - Lavar y cortar la lechuga.
   - Preparar el aderezo.
   - Mezclar todos los ingredientes.
   ```

2. **Output**:
   - A Notion page titled "Ensalada César" with:
     - Emoji: 🥗
     - Ingredients and instructions in separate sections
     - Notes (if any)
   - A photorealistic image of the dish saved locally.

