import { RouterProvider } from 'react-router-dom';

import ToastContainer from './components/ToastContainer';
import router from './router';

function App() {
  return (
    <>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
      <ToastContainer />
    </>
  );
}

export default App;
