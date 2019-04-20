import pandas as pd
from get_recipe_blocks import analyse_image
from parse_recipe import get_recipe_data
from pdf2image import convert_from_path
from PyPDF2 import PdfFileReader, PdfFileWriter
import os
import codecs
from PIL import ImageDraw
import pickle

f_book = open('Everyday-Healthy-Meals-Cookbook.pdf', 'rb')
reader = PdfFileReader(f_book)

res = []

pages = [9, 9, 10, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 29, 29,
	 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43,
	 45, 46, 47, 48, 48, 49, 50, 53, 54, 54, 55, 56, 57, 58]

#pages = [10, 10, 12]

#pages = [12]


pages = [p + 1 for p in pages]

i = 0
while i < len(pages):
	double = False
	if i + 1 < len(pages) and pages[i + 1] == pages[i]:
		double = True
		i += 1

	writer = PdfFileWriter()
	writer.addPage(reader.getPage(pages[i]))
	with open('temp.pdf', 'wb') as f:
		writer.write(f)

	image = convert_from_path('temp.pdf')[0].convert('LA').convert('RGB')
	os.system('pdf2txt.py temp.pdf > temp.txt')
	with codecs.open('temp.txt', 'r', encoding='utf-8') as f:
		recipe_txt = f.read()
	os.system('rm temp.pdf temp.txt')

	if double:
		w, h = image.size
		img1 = image.crop([0, 0, w / 2, h])
		img2 = image.crop([w / 2, 0, w, h])
		to_process = [img1, img2]
	else:
		to_process = [image]

	for j, image in enumerate(to_process):
		blocks = analyse_image(image)

		disp = image.copy()

		draw = ImageDraw.Draw(disp)
		for block in blocks:
			min_x = min([box[0] for box in block])
			max_x = max([box[0] + box[2] for box in block])
			min_y = min([box[1] for box in block])
			max_y = max([box[1] + box[3] for box in block])
			draw.rectangle([min_x, min_y, max_x, max_y], outline='green')

		#disp.show()

		#with open('blocks.pkl', 'wb') as f:
		#	pickle.dump(blocks, f)

		res.append(get_recipe_data(image, recipe_txt, blocks))
		print('Analyzed %d/%d of page %d' % (j + 1, len(to_process), pages[i] + 1))
	
	i += 1







res_df = pd.DataFrame(res)

res_df = pd.concat([res_df.drop(['macros'], axis=1),
                    res_df['macros'].apply(pd.Series)], axis=1)


res_df.to_csv('data/temp_everyday_healthy_meals.csv', index=False)

print('Done')
