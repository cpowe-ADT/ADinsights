interface FullPageLoaderProps {
  message?: string;
}

const FullPageLoader = ({ message = 'Loading…' }: FullPageLoaderProps) => {
  return (
    <div className="full-page-loader" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
};

export default FullPageLoader;
