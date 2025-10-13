import { ChangeEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import styles from "./Breadcrumbs.module.css";

type BreadcrumbItem = {
  label: string;
  to?: string;
};

type BreadcrumbsProps = {
  items: BreadcrumbItem[];
};

const CURRENT_CRUMB_VALUE = "__current__";

const Breadcrumbs = ({ items }: BreadcrumbsProps) => {
  const navigate = useNavigate();
  const lastIndex = items.length - 1;
  const currentValue =
    lastIndex >= 0 ? items[lastIndex]?.to ?? CURRENT_CRUMB_VALUE : CURRENT_CRUMB_VALUE;

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value;
    if (!next || next === CURRENT_CRUMB_VALUE) {
      return;
    }

    if (next) {
      navigate(next);
    }
  };

  return (
    <nav className={styles.breadcrumbs} aria-label="Breadcrumb">
      <ol className={styles.list}>
        {items.map((item, index) => {
          const isLast = index === lastIndex;
          return (
            <li key={`${item.label}-${index}`} className={styles.item}>
              {item.to && !isLast ? (
                <Link to={item.to} className={styles.link}>
                  {item.label}
                </Link>
              ) : (
                <span className={styles.current} aria-current="page">
                  {item.label}
                </span>
              )}
              {index < lastIndex ? <span className={styles.separator}>/</span> : null}
            </li>
          );
        })}
      </ol>
      <div className={styles.dropdown}>
        <label htmlFor="breadcrumb-select" className={styles.dropdownLabel}>
          Navigate to
        </label>
        <select
          id="breadcrumb-select"
          value={currentValue}
          onChange={handleChange}
          className={styles.dropdownSelect}
        >
          {items.map((item, index) => (
            <option
              key={`${item.label}-${index}`}
              value={item.to ?? CURRENT_CRUMB_VALUE}
              disabled={!item.to}
            >
              {item.label}
            </option>
          ))}
        </select>
      </div>
    </nav>
  );
};

export default Breadcrumbs;
