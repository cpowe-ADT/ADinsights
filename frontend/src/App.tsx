import { RouterProvider } from 'react-router-dom';

import { ToastProvider } from './components/ToastProvider';
import router from './router';

function App() {
  return (
    <ToastProvider>
      <RouterProvider router={router} />
    </ToastProvider>
  );
}

export default App;
