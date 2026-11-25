import { useEffect, useState } from 'react';
import { getStudents, type StudentRecord } from '../services/api';

export function useStudents() {
  const [students, setStudents] = useState<StudentRecord[]>([]);
  useEffect(() => { getStudents().then(setStudents).catch(() => setStudents([])); }, []);
  return students;
}
