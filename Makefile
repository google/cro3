default: generated/index.js

run: generated/index.js
	node generated/index.js

setup:
	npm install -g typescript

.PHONY : .FORCE

.FORCE :

generated/index.js: .FORCE
	tsc
