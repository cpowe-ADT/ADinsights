import path from 'node:path';

import { ConfigEnv, UserConfig, defineConfig, mergeConfig } from 'vite';

import baseConfig from './frontend/vite.config';

export default defineConfig((configEnv: ConfigEnv): UserConfig => {
  const resolvedBase =
    typeof baseConfig === 'function' ? baseConfig(configEnv) : (baseConfig as UserConfig);

  return mergeConfig(resolvedBase, {
    root: path.resolve(__dirname, 'frontend'),
    publicDir: path.resolve(__dirname, 'frontend/public'),
    build: {
      outDir: path.resolve(__dirname, 'frontend/dist'),
      emptyOutDir: true,
    },
  });
});
