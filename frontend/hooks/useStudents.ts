import { useEffect, useState } from 'react';
import { apiGet } from '../services/api';

export function useStudents() {
  const [students, setStudents] = useState([]);
  useEffect(() => { apiGet('/students').then(setStudents).catch(() => setStudents([])); }, []);
  return students;
}
