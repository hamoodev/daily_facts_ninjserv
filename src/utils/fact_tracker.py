import json
import hashlib

class FactTracker:
    def __init__(self, file_path):
        self.file_path = file_path
        self.used_facts = self.load_used_facts()
    
    def load_used_facts(self):
        """Load previously used facts from file"""
        try:
            with open(self.file_path, 'r') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()
    
    def save_used_facts(self):
        """Save used facts to file"""
        with open(self.file_path, 'w') as f:
            json.dump(list(self.used_facts), f)
    
    def fact_hash(self, fact):
        """Create a hash of the fact for comparison"""
        return hashlib.md5(fact.lower().strip().encode()).hexdigest()
    
    def is_fact_used(self, fact):
        """Check if a fact has been used before"""
        return self.fact_hash(fact) in self.used_facts
    
    def mark_fact_used(self, fact):
        """Mark a fact as used"""
        self.used_facts.add(self.fact_hash(fact))
        self.save_used_facts()