const { CheckerPlugin } = require('ts-loader')
const ESLintPlugin = require('eslint-webpack-plugin');
const path = require('path')


module.exports = {
  mode: 'development',
  resolve: {
    roots: [path.resolve('./src')],
    modules: ['node_modules'],
    extensions: ['.ts', '.tsx', '.js']
  },
  devtool: 'source-map',
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        loader: 'ts-loader',
      }
    ]
  },
  plugins: [new ESLintPlugin()],
  output: {
    filename: 'index.js'
  }
};
