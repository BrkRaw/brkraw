tests/tutorials:
	git clone https://github.com/BrkRaw/tutorials.git tests/tutorials

tests/tutorials/SampleData/20190724_114946_BRKRAW_1_1: tests/tutorials
	unzip -fo tests/tutorials/SampleData/20190724_114946_BRKRAW_1_1.zip \
			-d tests/tutorials/SampleData/

tests/tutorials/bids_map.csv: tests/tutorials/SampleData/20190724_114946_BRKRAW_1_1
	brkraw bids_helper tests/tutorials/SampleData/20190724_114946_BRKRAW_1_1 \
						tests/tutorials/bids_map

tests/tutorials/raw: tests/tutorials/bids_map.csv
	brkraw bids_convert tests/tutorials/SampleData/20190724_114946_BRKRAW_1_1 \
						tests/tutorials/bids_map.csv \
						--output tests/tutorials/raw

demo: tests/tutorials/raw