import { RouterProvider } from 'react-router-dom';

import ToastContainer from './components/ToastContainer';
import { ToastProvider } from './components/ToastProvider';
import router from './router';

function App() {
  return (
    <ToastProvider>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
      <ToastContainer />
    </ToastProvider>
  );
}

export default App;
