import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0', // Allows access from other devices on the network
    port: 9000, // Change this to any preferred port
    strictPort: true, // Ensures it fails if the port is in use
    cors: true, // Enables CORS
  }
});

