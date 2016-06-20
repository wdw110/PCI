#encoding=utf-8

import re
import math
from pysqlite2 import dbapi2 as sqlite

def getwords(doc):
	splitter = re.compile('\\W+')
	# 根据非字母字符进行单词拆分
	words = [s.lower() for s in splitter.split(doc) if len(s)>2 and len(s)<20]

	# 只返回一组不重复的单词
	return dict([(w,1) for w in words])

class classifier:
	def __init__(self,getfeatures,filename=None):
		# 统计特征/分类组合的数量
		self.fc = {}
		# 统计每个分类中的文档数量
		self.cc = {}
		self.getfeatures = getfeatures

	# 增加对特征/分类组合的计数值
	def incf(self,f,cat):
		count = self.fcount(f,cat)
		if count==0:
			self.con.execute("insert into fc values ('%s','%s',1)" % (f,cat))
		else:
			self.con.execute("update fc set count=%d where feature='%s' and category='%s'" % (count+1,f,cat))
		#self.fc.setdefault(f,{})
		#self.fc[f].setdefault(cat,0)
		#self.fc[f][cat] += 1

	# 增加对某一分类的计数值
	def incc(self,cat):
		count = self.catcount(cat)
		if count==0:
			self.con.execute("insert into cc values ('%s',1)" % (cat))
		else:
			self.con.execute("update cc set count=%d where category='%s'" % (count+1,cat))
		#self.cc.setdefault(cat,0)
		#self.cc[cat] += 1

	# 某一特征出现于某一分类中的次数
	def fcount(self,f,cat):
		res = self.con.execute('select count from fc where feature="%s" and category="%s"' % (f,cat)).fetchone()
		if res==None: return 0
		else: return float(res[0])
		#if f in self.fc and cat in self.fc[f]:
		#	return float(self.fc[f][cat])
		#return 0.0

	# 属于某一分类的内容项数量
	def catcount(self,cat):
		res = self.con.execute('select count from cc where category="%s"' % (cat)).fetchone()
		if res==None: return 0
		else: return float(res[0])
		#if cat in self.cc:
		#	return float(self.cc[cat])
		#return 0

	# 所有内容项的数量
	def totalcount(self):
		res = self.con.execute('select sum(count) from cc').fetchone()
		if res==None: return 0
		return res[0]
		#return sum(self.cc.values())

	# 所有分类的列表
	def categories(self):
		cur = self.con.execute('select category from cc')
		return [d[0] for d in cur]
		#return self.cc.keys()

	def train(self,item,cat):
		features = self.getfeatures(item)
		# 针对该分类为每个特征增加计数值
		for f in features:
			self.incf(f,cat)

		# 增加针对该分类的计数值
		self.incc(cat)
		self.con.commit()

	def fprob(self,f,cat):
		if self.catcount(cat)==0: return 0
		# 特征在分类中出现的总次数，除以分类中包含内容项的总数
		return self.fcount(f,cat)/self.catcount(cat)

	def weightedprob(self,f,cat,prf,weight=1.0,ap=0.5):
		# 计算当前的概率值
		basicprob = prf(f,cat)

		# 统计特征在所有分类中出现的次数
		totals = sum([self.fcount(f,c) for c in self.categories()])

		# 计算加权平均
		bp = ((weight*ap)+(totals*basicprob))/(weight+totals)
		return bp

	def setdb(self,dbfile):
		self.con = sqlite.connect(dbfile)
		self.con.execute('create table if not exists fc(feature,category,count)')
		self.con.execute('create table if not exists cc(category,count)')

class naivebayes(classifier):
	def __init__(self,getfeatures):
		classifier.__init__(self,getfeatures)
		self.thresholds = {}

	def docprob(self,item,cat):
		features = self.getfeatures(item)

		# 将所有特征的概率相乘
		p = 1
		for f in features:
			p *= self.weightedprob(f,cat,self.fprob)
		return p

	def prob(self,item,cat):
		catprob = self.catcount(cat)/self.totalcount()
		docprob = self.docprob(item,cat)
		return docprob*catprob

	def setthreshold(self,cat,t):
		self.thresholds[cat] = t

	def getthreshold(self,cat):
		if cat not in self.thresholds: return 1.0
		return self.thresholds[cat]

	def classify(self,item,default=None):
		probs = {}
		# 寻找概率最大的分类

		max = 0.0
		for cat in self.categories():
			probs[cat] = self.prob(item,cat)
			if probs[cat]>max:
				max = probs[cat]
				best = cat

		# 确保概率值超出域值*次大概率值
		for cat in probs:
			if cat == best: continue
			if probs[cat]*self.getthreshold(best)>probs[best]:
				return default
			return best

class fisherclassifier(classifier):
	def __init__(self,getfeatures):
		classifier.__init__(self,getfeatures)
		self.minimums = {}

	def cprob(self,f,cat):
		# 特征在该分类中出现的频率
		clf = self.fprob(f,cat)
		if clf==0: return 0

		# 特征在所有分类中出现的频率
		freqsum = sum([self.fprob(f,c) for c in self.categories()])

		# 概率等于特征在该分类中出现的频率除以总体频率
		p = clf/(freqsum)

		return p

	def fisherprob(self,item,cat):
		# 将所有的概率值相乘
		p = 1
		features = self.getfeatures(item)
		for f in features:
			p *= (self.weightedprob(f,cat,self.cprob))

		# 取自然对数，并乘以-2
		fscore = -2*math.log(p)

		# 利用倒置对数卡方函数求得概率
		return self.invchi2(fscore,len(features)*2)

	def invchi2(self,chi,df):
		m = chi/2.0
		sum = term = math.exp(-m)
		for i in range(1,df//2):
			term *= m/i
			sum += term
		return min(sum, 1.0)

	def setminimum(self,cat,min):
		self.minimums[cat] = min

	def getminimum(self,cat):
		if cat not in self.minimums: return 0
		return self.minimums[cat]

	def classify(self,item,default=None):
		# 循环遍历并寻找最佳结果
		best = default
		max = 0.0
		for c in self.categories():
			p = self.fisherprob(item,c)
			# 确保其超过下限值
			if p>self.getminimum(c) and p>max:
				best =c
				max = p
		return best

def sampletrain(cl):
	cl.train('Nobody owns the water.','good')
	cl.train('the quick rabbit jumps fences','good')
	cl.train('buy pharmaceuticals now','bad')
	cl.train('make quick money at the online casino','bad')
	cl.train('the quick brown fox jumps','good')