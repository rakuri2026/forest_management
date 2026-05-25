import React from 'react';
import { NepaliDatePicker as BsDatePicker } from 'react-nepali-datepicker-bs';
import 'react-nepali-datepicker-bs/dist/index.css';

interface NepaliDatePickerProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
}

export const NepaliDatePicker: React.FC<NepaliDatePickerProps> = ({ value, onChange, placeholder }) => {
  return (
    <BsDatePicker
      value={value ?? ''}
      onChange={(date: string) => onChange?.(date)}
      formatOptions={{
        separator: '/',
        format: 'YYYY/MM/DD',
      }}
      options={{
        calenderLocale: 'ne',
        valueLocale: 'en',
        closeOnSelect: true,
      }}
      placeholder={placeholder || 'मिति छान्नुहोस्'}
      theme="forest"
      style={{ width: '100%' }}
      todayIfEmpty={false}
    />
  );
};
