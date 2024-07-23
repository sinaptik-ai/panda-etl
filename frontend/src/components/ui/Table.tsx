import React from "react";

export interface Column<T> {
  header: string;
  accessor: keyof T | ((data: T) => React.ReactNode);
  label?: (data: T) => React.ReactNode;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  className?: string;
  onRowClick?: (data: any) => void;
}

export function Table<T>({
  data,
  columns,
  onRowClick,
  className = "",
}: TableProps<T>) {
  return (
    <table className={`min-w-full bg-white ${className} shadow rounded`}>
      <thead>
        <tr>
          {columns.map((column, index) => (
            <th key={index} className="py-2 px-4 border-b text-left">
              {column.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row: any, rowIndex) => (
          <tr key={rowIndex}>
            {columns.map((column, colIndex) => (
              <td
                key={colIndex}
                className={`py-2 px-4 border-b ${
                  onRowClick && "cursor-pointer"
                }`}
                onClick={() => {
                  onRowClick ? onRowClick(row) : null;
                }}
              >
                {column.label
                  ? column.label(row)
                  : typeof column.accessor === "function"
                  ? column.accessor(row)
                  : (row[column.accessor] as React.ReactNode) ?? "-"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
