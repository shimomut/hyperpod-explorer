all:

run:
	textual run --dev src/main.py

run-no-console:
	python src/main.py

console:
	textual console -x EVENT