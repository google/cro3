default: dist/index.js

dist/index.js : generated/index.js webpack.config.js Makefile
	webpack

generated/index.js : src/index.ts Makefile
	tsc

setup:
	npm install -g typescript webpack webpack-cli
	npm install
