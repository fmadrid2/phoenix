# Usage
# python Process_Discordant_SAM_File.py <Collapsed_TophatFusion_File> <Discordant_Reads.sam>

# requires python 3.4 with pandas, numpy, pysam packages

print("Importing Packages")
# Configure Enviroment
import pandas as pd
import numpy as np
import pysam
import sys
import os.path
import re
from subprocess import call

# Variables
# call_threshold = 3
# minimum_window_count = 2
window_size = int(sys.argv[3])
min_reads = 5

# tophat = int(sys.argv[4])
minimum_count_threshold = 0.75

print("Defining Functions")


# Function to process SAM file from SAMBLASTER DISCORDANT EXPORT
def bam_to_df(bam, chr=None, start=None, stop=None, file_name=None):
  file_name = os.path.basename(file_name)
  file_name = file_name.replace('\_R1\_Trinity\_sorted\.bam', '')
  print('Updated file name is ' + file_name)
  index = 0
  seq = []
  name = []
  r1_chr = []
  r1_pos = []
  r1_is_read1 = []
  r1_is_reversed = []
  r1_cigar = []
  r1_mapq = []
  r2_is_reversed = []
  r2_chr = []
  r2_pos = []
  frag_length = []
  r2_cigar = []
  r2_mapq = []
  pair_orientation = []
  for read in bam.fetch(chr, start, stop):
    # index = index + 1
    seq.append(read.query_sequence)
    name.append(file_name + ":" + read.query_name)  # +"_"+str(index))
    r1_chr.append(read.reference_name)
    r1_pos.append(read.reference_start)
    r1_is_read1.append(read.is_read1)
    r1_is_reversed.append(read.is_reverse)
    r1_cigar.append(read.cigarstring)
    r1_mapq.append(read.mapping_quality)
    r2_is_reversed.append(read.mate_is_reverse)
    r2_chr.append(read.next_reference_name)
    r2_pos.append(read.next_reference_start)
    frag_length.append(read.template_length)
    if read.has_tag('MC') == True:
      r2_cigar.append(read.get_tag('MC'))
    else:
      r2_cigar.append('NA')
    if read.has_tag('MQ') == True:
      r2_mapq.append(read.get_tag('MQ'))
    else:
      r2_mapq.append(255)
    if read.is_reverse is False and read.mate_is_reverse is True:
      pair_orientation.append("FR")
    elif read.is_reverse is True and read.mate_is_reverse is False:
      pair_orientation.append("RF")
    elif read.is_reverse is False and read.mate_is_reverse is False:
      pair_orientation.append("FF")
    elif read.is_reverse is True and read.mate_is_reverse is True:
      pair_orientation.append("RR")
    else:
      pair_orientation.append("Error")
    print(str(r1_cigar) + " and  " + str(name) + " mapq " + str(r1_mapq))
  return pd.DataFrame({'seq': seq,
                       'name': name,
                       'r1_pos': r1_pos,
                       'r1_chr': r1_chr,
                       'r1_is_read1': r1_is_read1,
                       'r1_is_reversed': r1_is_reversed,
                       'r1_cigar': r1_cigar,
                       'r1_mapq': r1_mapq,
                       'r2_is_reversed': r2_is_reversed,
                       'r2_chr': r2_chr,
                       'r2_pos': r2_pos,
                       'frag_length': frag_length,
                       'r2_cigar': r2_cigar,
                       'r2_mapq': r2_mapq,
                       'pair_orientation': pair_orientation})


# function to get junction break
def get_junctionBreak(cigarStr):
  # split cigar by M,S,H
  Mval = 0
  if (cigarStr != ''):
    tmp_cigar = cigarStr
    tmp_cigar = tmp_cigar.replace('H', 'M')
    tmp_cigar = tmp_cigar.replace('S', 'M')
    tmp_cigar = tmp_cigar.replace('I', 'M')
    tmp_cigar = tmp_cigar.replace('D', 'M')
    print(tmp_cigar)
    cigar_list = tmp_cigar.split('M')
    for values in cigar_list:
      print("vals = " + values)
      if (values != '' and cigarStr.find(str(values) + 'M') != -1):
        if (int(values) > Mval):
          Mval = int(values)
      if (Mval < window_size):
        print("Value lower than thr " + str(Mval))
  print("\n=====\n*************\n========\n")
  return Mval


# function to get junction break
def get_contigLength(cigarStr):
  con_len = 0
  if (cigarStr != ''):
    tmp_cigar = cigarStr
    tmp_cigar = tmp_cigar.replace('H', 'M')
    tmp_cigar = tmp_cigar.replace('S', 'M')
    tmp_cigar = tmp_cigar.replace('I', 'M')
    tmp_cigar = tmp_cigar.replace('D', 'M')
    print(tmp_cigar)
    cigar_list = tmp_cigar.split('M')
    for values in cigar_list:
      if (values != ''):
        con_len = con_len + int(values)
  return con_len


def reverseComplement(seq):
  # Reverse sequence string
  rseq = seq[::-1]

  # THIS NEEDS WORK NOT WORKING!!
  rseq = rseq.replace('A', 'B')
  rseq = rseq.replace('T', 'A')
  rseq = rseq.replace('B', 'T')

  rseq = rseq.replace('C', 'B')
  rseq = rseq.replace('G', 'C')
  rseq = rseq.replace('B', 'G')

  return rseq


# Function to check contigs
def check_contigs(contig_table, fastq_list, igregions, window_size=200, min_reads=5, contig_perc=0.1):
  # for i in range(len(contig_table)) :
  #    print(contig_table.loc[i, 'r1_cigar'])
  list_names = []
  final_table = pd.DataFrame()
  # final_table.columns = ['name','Gene_1','Gene_2','seq', 'cigar_1','cigar_2','length_1','length_2','R1_count_1','R2_count_1','R1_count_2','R1_count_2'];
  final_table['name'] = ''
  final_table['Gene_1'] = ''
  final_table['Gene_2'] = ''
  final_table['seq'] = ''
  final_table['cigar_1'] = ''
  final_table['cigar_2'] = ''
  final_table['length_1'] = ''
  final_table['length_2'] = ''
  final_table['R1_count_1'] = ''
  final_table['R2_count_1'] = ''
  final_table['R2_count_2'] = ''
  final_table['R2_count_1'] = ''

  for row in contig_table.index:
    r1_cigar = contig_table.at[row, 'r1_cigar']
    name = contig_table.at[row, 'name']
    if (name not in list_names):
      list_names.append(name)

    # add data to
    final_table.at[row, 'name'] = name
    final_table.at[row, 'seq'] = contig_table.at[row, 'seq']
    # loop through to find contigs
  ftableIndex = 0
  for names in list_names:
    ftableIndex = ftableIndex + 1
    # extract by name
    print(names)

    contig_table_by_read = contig_table[(contig_table.name == names)]
    # if contigs aligns to multiple locations
    count = len(contig_table_by_read.index)
    if (count > 1):  # was 1 but now trying to include all
      print(contig_table_by_read)
      # get breakpoint on contig?
      # check their locations
      loop_var = 0
      for contig_row in contig_table_by_read.index:
        contig_chr = contig_table_by_read.at[contig_row, 'r1_chr']
        contig_pos = contig_table_by_read.at[contig_row, 'r1_pos']
        mygene = isKnownTx(contig_chr, int(contig_pos), igregions)

        print("contig_chr=" + contig_chr + "contig_pos " + str(contig_pos) + mygene)

        mVal = get_junctionBreak(contig_table_by_read.at[contig_row, 'r1_cigar'])
        if (mVal < window_size):
          print("Value lower than thr " + str(mVal))
        juncbreak = mVal

        contig_len = get_contigLength(contig_table_by_read.at[contig_row, 'r1_cigar'])

        contig = contig_table_by_read.at[contig_row, 'seq']
        namesSplit = names.split(':')
        fastq = namesSplit[0]
        fastq = fastq.replace('Trinity_sorted.bam', '001.fastq.gz')
        # fastq = namesSplit #namesSplit[0]+ "_001_fastq.gz"
        ffastq = ''
        for fqs in fastq_list:
          if (fastq in fqs):
            ffastq = fqs
        print("\nfastq full is " + str(ffastq))
        # fastq_file = fqs[]
        print("\nfastq name is " + fastq)
        # print("\nfastq full is " + fastq)

        # extract 25mers left and right of contig
        jright = juncbreak + 12
        jleft = juncbreak - 13

        # r1  = contig[juncbreak: jright: 1]
        # r2 = contig[jleft: juncbreak: 1]
        rr = contig[jleft:jright:1]

        r1_count = getReadsatjunction(rr, contig, ffastq)
        ffastq_2 = ffastq
        ffastq_2.replace("_R1", "_R2")
        r2_count = getReadsatjunction(rr, contig, ffastq_2)
        print("read count is " + str(r1_count))

        if (loop_var == 0 and mVal >= window_size):
          # add data to
          # final_table.at[row,'name'] = name
          # final_table.at[row,'seq'] = contig_table.at[row,'seq']
          # final_table.at[[ftableIndex],'name']=contig_table_by_read.at[contig_row,'name']
          # final_table.at[[ftableIndex],'seq']=contig
          final_table.at[[ftableIndex], 'cigar_1'] = contig_table_by_read.at[contig_row, 'r1_cigar']
          final_table.at[[ftableIndex], 'Gene_1'] = mygene
          final_table.at[[ftableIndex], 'length_1'] = mVal
          final_table.at[[ftableIndex], 'percent_of_contig_at_Gene_1'] = mVal * 100 / contig_len
          final_table.at[[ftableIndex], 'R1_count_1'] = r1_count
          final_table.at[[ftableIndex], 'R2_count_1'] = r2_count
          final_table.at[[ftableIndex], 'pos_1_start'] = contig_table_by_read.at[contig_row, 'r1_pos']
          final_table.at[[ftableIndex], 'pos_1_end'] = contig_table_by_read.at[contig_row, 'r1_pos'] + mVal
          final_table.at[[ftableIndex], 'IgTxCalled'] = 1
          # loop_var = loop_var + 1
        elif (loop_var == 1 and mVal >= window_size):
          # final_table[[ftableIndex],'seq']=contig
          final_table.at[[ftableIndex], 'cigar_2'] = contig_table_by_read.at[contig_row, 'r1_cigar']
          final_table.at[[ftableIndex], 'Gene_2'] = mygene
          final_table.at[[ftableIndex], 'length_2'] = mVal
          final_table.at[[ftableIndex], 'percent_of_contig_at_Gene_2'] = mVal * 100 / contig_len
          final_table.at[[ftableIndex], 'R1_count_2'] = r1_count
          final_table.at[[ftableIndex], 'R2_count_2'] = r2_count
          final_table.at[[ftableIndex], 'pos_2_start'] = contig_table_by_read.at[contig_row, 'r1_pos']
          final_table.at[[ftableIndex], 'pos_2_end'] = contig_table_by_read.at[contig_row, 'r1_pos'] + mVal
          if (count > 1):
            final_table.at[[ftableIndex], 'IgTxCalled'] = 1

        loop_var = loop_var + 1
    elif (count == 1):  # Cases where contigs dont align to more than one location
      contig_elem =
  return final_table


# Function to check if given  location (chr:pos) is in list of IgTx regions
def isKnownTx(qchr, qpos, listofRegions):
  txGene = ''
  chr_region = listofRegions[(listofRegions.chr == qchr)]
  for row in chr_region.index:
    if ((chr_region.at[row, 'start'] <= qpos) and (chr_region.at[row, 'stop'] >= qpos)):
      if (qchr == 'chr14'):
        txGene = "IGH"
      if (qchr == 'chr2'):
        txGene = "IGK"
      if (qchr == 'chr22'):
        txGene = "IGL"
      if (qchr == 'chr4'):
        txGene = "NSD2"
      if (qchr == 'chr11'):
        txGene = "CCND1"
      if (qchr == 'chr12'):
        txGene = "CCND2"
      if (qchr == 'chr6'):
        txGene = "CCND3"
      if (qchr == 'chr16'):
        txGene = "MAF"
      if (qchr == 'chr8' and qpos >= 142918584 and qpos <= 143925832):
        txGene = "MAFA"
      if (qchr == 'chr20'):
        txGene = "MAFB"
      if (qchr == 'chr8' and qpos >= 124987758 and qpos <= 129487754):
        txGene = "MYC"
  return txGene


def getReadsatjunction(region, contig, fastq):
  r1_count = 0
  # grep region1 from fastq
  print(region)
  tmp_file = "/scratch/snasser/testTxVariates/r1counts.txt"
  status = call("/scratch/snasser/testTxVariates/findinfile.sh " + fastq + " " + region + " " + tmp_file,
                shell=True)  # "zcat "+ fastq + " | grep " + r1 + " | wc -l ") # > "+tmp_file)
  if status < 0:
    print("### Cat Command Failed....now exiting!!")
    sys.exit(-1)
  else:
    with open("r1counts.txt", "r") as myfile:
      data = myfile.readlines()
      r1_count = int(data[0])
      # print("read count is "+ str(r1_count))
  return r1_count


# END FUNCTION DEFINITIONS

print("Importing Data")

print("Reading SAM File")
# Create python object for the SAM file
bam_list_string = sys.argv[1]
bam_list = bam_list_string.split(',')
# get fastq
fastq_str = sys.argv[2]
fastq_list = fastq_str.split(',')
# get Ig/parter bed file
ig_headers = ['chr', 'start', 'stop', 'name']
igregions = pd.read_csv(sys.argv[4], sep="\t", header=None, names=ig_headers)

full_table = pd.DataFrame()
results_full_table = pd.DataFrame()
index_sam = 0
table_hrd = []
for assm_sam_file in bam_list:
  samfile = pysam.AlignmentFile(assm_sam_file, "r")

  print("Creating SAM File Table")
  # Call Function to convert SAM file into pandas dataframe

  table = bam_to_df(samfile, file_name=assm_sam_file)
  table_hrd = list(table.columns)
  results_table = check_contigs(table, fastq_list, igregions, window_size, min_reads)
  if (index_sam == 0):
    full_table = table
    results_full_table = results_table
  else:
    print("Merging Regional bam")
    frames = [full_table, table]
    full_table = pd.concat(frames)
    frames2 = [results_full_table, results_table]
    results_full_table = pd.concat(frames2)
    # full_table = full_table.merge(table, left_on='name', right_on='name')
  index_sam = index_sam + 1

full_table.reset_index(drop=True)
full_table.set_index('name')  # ["name"])

# generate common bam
# Sort the bam
# write bam to file
samfile = pysam.AlignmentFile(bam_list[0], "rb")
combinedreads = pysam.AlignmentFile("allpaired.bam", "wb", template=samfile)
for row in full_table.index:
  # "combine in order of sam"
  col_range = table.columns.isin(table_hrd)
#   print(table_hrd)
# ['seq', 'name', 'r1_pos', 'r1_chr', 'r1_is_read1', 'r1_is_reversed', 'r1_cigar', 'r1_mapq', 'r2_is_reversed', 'r2_chr', 'r2_pos', 'frag_length', 'r2_cigar', 'r2_mapq', 'pair_orientation']
#    bamline = str(full_table.at[row,'name'])+"2048"+str(full_table.at[row,'r1_chr'])+ str(full_table.at[row,'r1_pos'])+str(full_table.at[row,'pair_orientation'])
#    print(bamline)
#    combinedreads.write(join(map(str, bamline)))
# pysam.sort()
print("****************")
full_table.to_csv("MergedTableAllRegions.txt", sep="\t", index=False, na_rep=0, float_format='%.0f')
print(full_table)

results_full_table.to_csv("ContigResults.txt", sep="\t", index=False, na_rep=0, float_format='%.0f')
print("Test Done")

