module.exports = {
  apps: [{
    name: 'bitever-proxy',
    script: '/root/.pyenv/versions/3.12.6/bin/uvicorn',
    args: 'proxy:app --host 0.0.0.0 --port 8888',
    cwd: '/root/bitever-esplora',
    interpreter: 'python3',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production'
    }
  }]
};
