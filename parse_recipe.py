import locale
locale.setlocale(locale.LC_ALL, 'C')
from tesserocr import PyTessBaseAPI, RIL
from PIL import ImageDraw
import numpy as np
from itertools import combinations, product
import re

ingredient_id = re.compile(r'\d+\s*[^\.]')
instruction_id = re.compile(r'\d+\s*\.')

api = PyTessBaseAPI()

fractions = {
	'½': '1/2',
	'⅓': '1/3',
	'⅔': '2/3',
	'¼': '1/4',
	'¾': '3/4',
	'⅕': '1/5',
	'⅖': '2/5',
	'⅗': '3/5',
	'⅘': '4/5',
	'⅙': '1/6',
	'⅚': '5/6'
}


def get_recipe_data(image, pdf_text, blocks):
	api.SetImage(image)
	blocks.sort(key=lambda block: np.min([box[1] for box in block]))

	texts = []

	for block in blocks:
		min_x = min([box[0] for box in block])
		max_x = max([box[0] + box[2] for box in block])
		min_y = min([box[1] for box in block])
		max_y = max([box[1] + box[3] for box in block])
		#draw.rectangle([min_x, min_y, max_x, max_y], outline='green')
		api.SetRectangle(min_x - 5, min_y - 5, max_x - min_x + 10, max_y - min_y + 10)
		texts.append(api.GetUTF8Text())

	blocks = [blocks[i] for i in range(len(blocks)) if texts[i].strip()]
	texts = [texts[i] for i in range(len(texts)) if texts[i].strip()]

	servings = get_servings(texts)

	return {
		'name': get_title(blocks, texts),
		'description': get_description(blocks, texts),
		'instructions': get_instructions(texts),
		'ingredients': get_ingredients(texts, pdf_text),
		'macros': get_macros(texts, servings)
	}


def get_block_x(block):
	return min([box[0] for box in block])

def get_block_y(block):
	return min([box[1] for box in block])

def mean_block_height(block):
        return np.mean([box[3] for box in block])

def get_title_block(blocks):
	return np.argmax([mean_block_height(block) for block in blocks])

def get_title(blocks, texts):
	return texts[get_title_block(blocks)].upper().strip().replace('\n', ' ')

def get_description(blocks, texts):
	i = get_title_block(blocks) + 1
	description = []
	done = False
	while not done:
		description.append(texts[i].strip())
		i += 1
		if i == len(blocks):
			done = True
		if abs(get_block_x(blocks[i - 1]) - get_block_x(blocks[i])) > 5 or abs(get_block_y(blocks[i - 1]) - get_block_y(blocks[i])) > 2 * np.mean([mean_block_height(blocks[i - 1]), mean_block_height(blocks[i])]):
			done = True

	return ' '.join(description).strip().replace('\n', ' ')
	return texts[get_title_block() + 1].strip().replace('\n', ' ')

def is_ingredientlike(line):
	return ingredient_id.match(line) is not None


def count_ingredientlike(lines):
	return [is_ingredientlike(line) for line in lines].count(True)


def extract_ingredients(text, prev_ingredients, pdf_text):
	text = text.lower()
	lines = list(filter(lambda x: x, map(lambda x: x.strip(), text.split('\n'))))
	if not lines:
		return []

	isingredients = lines[0] == 'ingredients'

	if len(lines) <= 3:
		try_fix = fix_ingredient(lines[0], pdf_text)
		if (try_fix.lower() != lines[0].lower() or is_ingredientlike(try_fix)) and 'serving' not in lines[0].lower():
			return lines
	
	if not is_ingredientlike(lines[0]):
		lines = lines[1:]

	count_ingredientlike_res = count_ingredientlike(lines)
	if isingredients or count_ingredientlike_res >= 2 or (prev_ingredients and count_ingredientlike_res > 0):
		return lines

	return []

def fix_ingredient(ingredient, pdf_text):
	m = re.match(r'([^\s]+)\s+(.+)', ingredient)
	if not m:
		return ingredient
	a, k = m.groups()
	if len(a) > 2:
		return ingredient

	m = re.search(r'([^\s]+)\s+%s' % re.escape(k), pdf_text)
	if not m:
		return ingredient
	res = '%s %s' % (m.groups()[0], k)
	for fraction in fractions.keys():
		res = res.replace(fraction, fractions[fraction])

	return res

def merge_ingredients(ingredients):
	i = 1
	while i < len(ingredients):
		if not is_ingredientlike(ingredients[i]):
			ingredients[i - 1] += ' %s' % ingredients[i]
			del ingredients[i]
		else:
			i += 1

	return ingredients

def get_ingredients(texts, pdf_text):
	ingredients = []
	new_ingredients = []
	for text in texts:
		if not text:
			continue
		new_ingredients = extract_ingredients(text, len(new_ingredients) > 0, pdf_text)
		ingredients += new_ingredients
	return merge_ingredients([fix_ingredient(ingredient, pdf_text) for ingredient in ingredients])

def is_instructionlike(line):
	return instruction_id.match(line) is not None

def extract_instructions(text):
	lines = list(filter(lambda x: x, map(lambda x: x.strip(), text.split('\n'))))
	if not lines:
		return ''
	if not is_instructionlike(lines[0]):
		lines = lines[1:]
	if any([is_instructionlike(line) for line in lines]):
		return ' '.join(lines)

	return ''

def get_instructions(texts):
	instructions = []
	for text in texts:
		instructions.append(extract_instructions(text))

	res = ' '.join(filter(lambda x: x, instructions))
	instructions = re.compile(r'(\d+\..+?(?=(?:\d+\.|$)))')
	return ' '.join(sorted(list(map(lambda x: x.strip(), instructions.findall(res))), key=lambda x: int(re.match(r'(\d+)\.', x).groups()[0])))

def get_macro(texts, regex):
	for text in texts:
		text = text.lower()
		m = re.search(regex, text)
		if m:
			return int(m.groups()[0])

	return 0

def get_calories(texts):
	return get_macro(texts, r'calories\s(\d+)')

def get_carbs(texts):
	return get_macro(texts, r'carbohydrate\s(\d+)')

def get_protein(texts):
	return get_macro(texts, r'protein\s(\d+)')

def get_fat(texts):
	return get_macro(texts, r'total\sfat\s(\d+)')

def get_macros(texts, servings):
	calories = get_calories(texts)
	carbs = get_carbs(texts)
	protein = get_protein(texts)
	fat = get_fat(texts)
	return {'calories': calories * servings, 'carbs': carbs * servings, 'protein': protein * servings, 'fat': fat * servings}

def get_servings(texts):
	for text in texts:
		text = text.lower()
		m = re.search(r'makes (\d+) servings', text)
		if m:
			return int(m.groups()[0])

	return 1

