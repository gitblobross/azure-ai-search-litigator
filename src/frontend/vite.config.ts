import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    optimizeDeps: {
        esbuildOptions: {
            target: "esnext"
        }
    },
    build: {
        outDir: "../backend/static",
        emptyOutDir: true,
        sourcemap: true,
        target: "esnext",
        chunkSizeWarningLimit: 2000,
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (id.includes('node_modules')) {
                        if (id.includes('react')) {
                            return 'react-vendor';
                        }
                        if (id.includes('azure-search-documents') || id.includes('azure-storage-blob')) {
                            return 'azure-sdk';
                        }
                        return 'vendor';
                    }
                }
            }
        }
    },
    server: {
        proxy: {
            "/chat": {
                target: "http://localhost:5000"
            },
            "/list_indexes": {
                target: "http://localhost:5000"
            },
            "/get_citation_doc": {
                target: "http://localhost:5000"
            }
        }
    }
});
