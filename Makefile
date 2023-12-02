all:

run:
	python src/main.py

dev-run:
	textual run --dev src/main.py

console:
	textual console -x EVENT