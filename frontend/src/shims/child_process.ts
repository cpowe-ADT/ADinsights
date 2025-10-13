export const spawn = () => {
  throw new Error('child_process.spawn is not supported in the browser build')
}

export default { spawn }
