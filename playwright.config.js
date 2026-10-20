module.exports = {
  testDir: '.',
  testMatch: 'live-audit.spec.js',
  workers: 1,
  reporter: 'line',
  use: {
    browserName: 'chromium',
    headless: true,
    launchOptions: { channel: 'chrome', args: ['--no-proxy-server'] },
  },
};
