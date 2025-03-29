# import base64
import os
from io import BytesIO

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

contents = """A wide-format, highly detailed, ultra-photorealistic image of a freshly prepared dish
        placed prominently in the center of a rustic wooden table. The dish is the clear focus,
        beautifully lit with soft natural light that enhances its color and texture. Surrounding
        it, in the background or off to the side, a few of the raw ingredients used in the recipe
        are arranged casually. The atmosphere is warm and natural, evoking the feeling of a cozy, 
        artisanal kitchen. Don't include any text in the image. The recipe is: """

# contents = """ Make a highly detailed and photorealistic image of this recipe. Don't include any
# text, It's just so you get what the recipe is about. Make it in a wide format. The recipe: """

recipe = """ Title: Flan al caramelo - crème renversée au caramel
Portions: 8
Vegetarian: no
Ingredients:
- Azúcar 250 GR
- Esencia de vainilla C/N
- Huevo 6 UN
- Leche 1LTS
- Yema de huevo 4 UN
- Agua 60 CC
- Azúcar 200 GR
- Jugo de limón C/N
Instructions:
- Hervir la leche con la mitad del azúcar.
- Mezclar 6 huevos con 4 yemas, la otra mitad del azúcar y la esencia de vainilla.
- Agregar a la mezcla anterior la leche de a poco revolviendo al mismo tiempo.
- Verter la mezcla obtenida en un molde caramelizado.
- Cocinar a Baño María a 160°C durante 35 minutos.
- Hidratar el azúcar con agua y unas gotas de jugo de limón.
- Espumar cuando rompe el hervor.
- Cocinar hasta punto caramelo. """

prompt = contents + "\n\n" + recipe

response = client.models.generate_content(
    model="gemini-2.0-flash-exp-image-generation",
    contents=prompt,
    config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
)

for part in response.candidates[0].content.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = Image.open(BytesIO((part.inline_data.data)))
        image.save("gemini-native-image.png")
        image.show()
