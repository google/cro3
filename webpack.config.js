module.exports = {
  mode: 'development',
  resolve: {
    modules: ['node_modules']
  },
  entry: './generated/index.js',
  output: {
    filename: 'index.js'
  },
  devtool: 'source-map'
};
