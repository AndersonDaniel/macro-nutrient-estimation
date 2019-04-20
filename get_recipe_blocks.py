import locale
locale.setlocale(locale.LC_ALL, 'C')
from tesserocr import PyTessBaseAPI, RIL
from PIL import ImageDraw
import numpy as np
from itertools import combinations, product
import pickle
from numba import jit

api = PyTessBaseAPI(psm=4)

from pdf2image import convert_from_path

MARGIN = .5

#image = convert_from_path('temp2.pdf')[0]

#w, h = image.size
#test = image.crop([0, 0, w / 2, h]).convert('LA').convert('RGB')
#test = image.crop([w / 2, 0, w, h]).convert('LA').convert('RGB')
#test = image.copy().convert('LA').convert('RGB')

#api.SetImage(test)

#draw = ImageDraw.Draw(test)

#boxes = api.GetComponentImages(RIL.WORD, True)
#blocks = [[box] for im, box, _, _ in boxes]

#@jit(forceobj=True)
def get_box_points(box):
	points = []
	points.append((box[0], box[1]))
	points.append((box[0] + box[2], box[1]))
	points.append((box[0], box[1] + box[3]))
	points.append((box[0] + box[2], box[1] + box[3]))

	return points

#@jit(forceobj=True)
def dist(p1, p2):
	return np.linalg.norm(np.array(p1) - np.array(p2))

#@jit(forceobj=True)
def box_dist(box1, box2):
	box1_pts = get_box_points(box1)
	box2_pts = get_box_points(box2)
	return np.min([dist(p1, p2) for p1, p2 in product(box1_pts, box2_pts)])

#@jit(forceobj=True)
def block_dist(block1, block2):
	return min([box_dist(b1, b2) for b1, b2 in product(block1, block2)])

#@jit(forceobj=True)
def inner_block_dist(block):
	if len(block) < 2:
		return None
	
	dists = []
	for i in range(len(block)):
		dists.append(np.min([box_dist(block[i], block[j]) for j in range(len(block)) if i != j]))

	return np.mean(dists)

#@jit(forceobj=True)
def mean_block_height(block):
	return np.mean([box[3] for box in block])

def analyse_image(image):
	api.SetImage(image)
	boxes = api.GetComponentImages(RIL.WORD, True)
	blocks = [[[box['x'], box['y'], box['w'], box['h']]] for im, box, _, _ in boxes]

	done = False
	while not done:
		merged = False
		#mean_block_heights = [mean_block_height(block) for block in blocks]
		#mean_block_inner_dists = [inner_block_dist(block) for block in blocks]
		for i in range(len(blocks)):
			current_block_inner_dist = inner_block_dist(blocks[i])
			current_block_mean_height = mean_block_height(blocks[i])
			dist_lim = 30
			if current_block_inner_dist is not None:
				dist_lim = (1 + MARGIN) * current_block_inner_dist
			block_dists = [block_dist(blocks[i], blocks[j]) if i != j else 10000 for j in range(len(blocks))]
			for j in np.argsort(block_dists):
				if i == j:
					continue

				other_block_height = mean_block_height(blocks[j])
				if block_dists[j] <= dist_lim and current_block_mean_height >= (1 - MARGIN) * other_block_height and current_block_mean_height <= (1 + MARGIN) * other_block_height:
					blocks[i] += blocks[j]
					del blocks[j]
					merged = True
					break
			if merged:
				break
		if not merged:
			done = True
		
	return blocks


#for block in blocks:
#	min_x = min([box['x'] for box in block])
#	max_x = max([box['x'] + box['w'] for box in block])
#	min_y = min([box['y'] for box in block])
#	max_y = max([box['y'] + box['h'] for box in block])
#	draw.rectangle([min_x, min_y, max_x, max_y], outline='green')


#test.show()

#with open('blocks.pkl', 'wb') as f:
#	pickle.dump(blocks, f)

