import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/iqcarbon.github.io/',
  build: {
    outDir: 'dist',
  },

});
