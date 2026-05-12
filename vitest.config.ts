import path from 'node:path'

import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    exclude: ['.ttadk/**', 'node_modules/**'],
    setupFiles: ['./src/test/setup.ts'],
  },
})
