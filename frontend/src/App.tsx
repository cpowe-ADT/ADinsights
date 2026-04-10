import { RouterProvider } from 'react-router-dom';

import ToastViewport from './components/ToastViewport';
import router from './router';

function App() {
  return (
    <>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
      <ToastViewport />
    </>
  );
}

export default App;
