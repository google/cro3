default: dist/index.js

dist/index.js : generated/index.js webpack.config.js
	webpack

generated/index.js : src/index.ts
	tsc

setup:
	npm install -g typescript webpack webpack-cli
	npm install
