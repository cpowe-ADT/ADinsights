const requiredEnvVars = ['CANVA_API_KEY'];

function checkConfiguration(env = process.env) {
  const missing = requiredEnvVars.filter((name) => !env[name]);
  if (missing.length > 0) {
    console.warn(
      `Canva export disabled. Missing environment variables: ${missing.join(', ')}. ` +
        'Populate them in a local .env file based on .env.example to enable the integration.'
    );
    return false;
  }

  return true;
}

async function exportDesignStub(payload = {}) {
  if (!checkConfiguration()) {
    console.info('Skipping Canva export stub because configuration is incomplete.');
    return { status: 'skipped', reason: 'missing_configuration' };
  }

  console.info('Canva export stub invoked with payload:', JSON.stringify(payload));
  console.info('Replace this stub with an authenticated Canva upload when the API contract is finalized.');

  return { status: 'noop', message: 'Stub executed successfully' };
}

module.exports = {
  checkConfiguration,
  exportDesignStub,
};
