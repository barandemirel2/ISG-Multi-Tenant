import React, { useEffect, useState } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

export const CountUp = ({ to, duration = 1.5, suffix = "" }) => {
  const spring = useSpring(0, { duration: duration * 1000, bounce: 0 });
  const displayValue = useTransform(spring, (current) => Math.round(current));
  const [value, setValue] = useState(0);

  useEffect(() => {
    spring.set(to);
  }, [to, spring]);

  useEffect(() => {
    const unsubscribe = displayValue.on("change", (v) => setValue(v));
    return () => unsubscribe();
  }, [displayValue]);

  return (
    <motion.span className="font-mono tabular-nums">
      {value}{suffix}
    </motion.span>
  );
};
