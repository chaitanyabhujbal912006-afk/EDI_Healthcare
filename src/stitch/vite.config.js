import { defineConfig } from 'vite';

const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000';

export default defineConfig({
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      }
    }
  },
  preview: {
    host: true,
    port: 5173
  },
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        login: 'login_sleek_redesign/code.html',
        dashboard: 'dashboard_sleek/code.html',
        master_parser: 'master_parser_sleek/code.html',
        remittance_835: '835_remittance_sleek/code.html',
        enrollment_834: '834_enrollment_sleek/code.html',
        claims_837: '837_claims_view/code.html',
        notifications: 'notifications/code.html',
        settings: 'settings/code.html',
        user_profile: 'user_profile/code.html',
        documentation: 'documentation/code.html',
        help_center: 'help_center/code.html'
      }
    }
  }
});
