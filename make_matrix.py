#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Make matrix"""
import os
import sys

import numpy as np
import pysam as ps
import pandas as pd

fas_file = "test/example.fa"
vcf_file = "test/example.vcf.gz"
gtf_file = "test/example.gtf.gz"
bam_file = "test/example.bam"

class UnknownStrandError(Exception):
    pass

class LengthError(Exception):
    pass

class NonDictError(Exception):
    pass

# A made matrix transforming alleles into matrix, which will make life easier
TRANS_MATRIX = {
    "AA":(1, 0, 0, 0), "AC":(1, 1, 0, 0), "AG":(1, 0, 1, 0), "AT":(1, 0, 0, 1),
    "aa":(1, 0, 0, 0), "ac":(1, 1, 0, 0), "ag":(1, 0, 1, 0), "at":(1, 0, 0, 1),
    "CA":(1, 1, 0, 0), "CC":(0, 1, 0, 0), "CG":(0, 1, 1, 0), "CT":(0, 1, 0, 1),
    "ca":(1, 1, 0, 0), "cc":(0, 1, 0, 0), "cg":(0, 1, 1, 0), "ct":(0, 1, 0, 1),
    "GA":(1, 0, 0, 1), "GC":(0, 1, 1, 0), "GG":(0, 0, 1, 0), "GT":(0, 0, 1, 1),
    "ga":(1, 0, 0, 1), "gc":(0, 1, 1, 0), "gg":(0, 0, 1, 0), "gt":(0, 0, 1, 1),
    "TA":(1, 0, 0, 1), "TC":(0, 1, 0, 1), "TG":(0, 0, 1, 1), "TT":(0, 0, 0, 1),
    "ta":(1, 0, 0, 1), "tc":(0, 1, 0, 1), "tg":(0, 0, 1, 1), "tt":(0, 0, 0, 1),
    "NN":(0, 0, 0, 0), "nn":(0, 0, 0, 0)
}

NT_VEC_DICT = { # Encoded neucliotide
    "A": [1, 0, 0, 0], "C": [0, 1, 0, 0], "G": [0, 0, 1, 0], "T": [0, 0, 0, 1]
}

VEC_NT_DICT = {
    (1, 0, 0, 0): "A", (0, 1, 0, 0): "C", (0, 0, 1, 0): "G", (0, 0, 0, 1): "T"
}

def _make_variant_dict(variants):  # TODO: check data type of var.pos and var.chr
    record_dict = {(var.chrom, var.pos): var for var in variants}  # FIXME: could be duplicated positions
    return record_dict

def _parse_sample_genotype(samples, alleles):
    sample_dict = {key: _decode_vcf_haps(alleles, val["GT"]) for key, val in samples.items()}
    return sample_dict

def _decode_vcf_haps(alleles, code):
    return (alleles[code[0]], alleles[code[1]])

def _encode_hap_into_vec(hap):
    return NT_VEC_DICT.get(hap, [0, 0, 0, 0])

def _decode_vec_into_hap(vec, dft="N"):
    return VEC_NT_DICT.get(tuple(vec), dft)

def matrix_factory(seq, var_hash, chrom, shift, target_samples=["gonl-100a"]):
    # FIXME: `shift` should be determined by strand???
    if not isinstance(var_hash, dict):
        raise NonDictError  # TODO: a concrete sub-class of TypeError

    if not isinstance(target_samples, (list, tuple)):
        target_samples = [target_samples]

    target_sample_allele_vec = {}

    for _each_sample in target_samples:
        _allele_vec = []
        for _idx, base in enumerate(seq):
            pos = _idx + shift
            if (chrom, pos) in var_hash:
                var_record = var_hash[(chrom, pos)]  # TODO: func to handle multi alts
                samples, alleles = var_record.samples, var_record.alleles
                samples_alleles_dict = _parse_sample_genotype(samples, alleles)
                allele_a_char, allele_b_char = samples_alleles_dict.get(_each_sample)
            else:
                allele_a_char, allele_b_char = base, base
            
            _allele_vec.append(_encode_hap_into_vec(allele_a_char) + _encode_hap_into_vec(allele_b_char))

        target_sample_allele_vec[_each_sample] = _allele_vec
    
    return target_sample_allele_vec

def make_matrix(inter_hand, seq_hand, var_hand, aln_hand, with_orf=False, contig="1",
                up_shift=10000, dw_shift=200000, merged=True, interval_type="gene",
                target_gene="ENSG00000227232"):
    """Make input matrix"""
    var_header = var_hand.header
    # var_sample = var_hand.samples

    gene_matrix = {}
    for field in inter_hand.fetch("1"):
        # Important fields
        attrbutes = field.attributes
        gene_id = field.gene_id
        contig = field.contig
        strand = field.strand
        start = field.start
        end = field.end

        if field.feature != interval_type:
            continue
        
        if gene_id not in target_gene:
            continue

        if up_shift:
            up_start = (int(start) - 1) - up_shift
            up_end = int(start) - 1
            up_seq = seq_hand.fetch(reference=contig, start=up_start, end=up_end)
            up_vars = var_hand.fetch(contig=contig, start=up_start, stop=up_end, reopen=True)
            up_vars_hash = _make_variant_dict(up_vars)
            up_matrix = matrix_factory(up_seq, up_vars_hash, contig, up_start)
        else:
            up_matrix = []
        
        iv_start, iv_end = start, end
        iv_seq = seq_hand.fetch(reference=contig, start=iv_start, end=iv_end)
        iv_aln = aln_hand.fetch(reference=contig, start=iv_start, end=iv_end)

        if dw_shift:
            dw_start = int(end) + 1
            dw_end = (int(end) + 1) + dw_shift
            dw_seq = seq_hand.fetch(reference=contig, start=dw_start, end=dw_end)
            dw_vars = var_hand.fetch(contig=contig, start=dw_start, stop=dw_end, reopen=True)
            dw_vars_hash = _make_variant_dict(dw_vars)
            dw_matrix = matrix_factory(dw_seq, dw_vars_hash, contig, dw_start)
        else:
            dw_matrix = []

        # TODO: should yield a merged metrix of upstream and downstream
        if strand == '-':
            gene_matrix[gene_id] = {"upstream": dw_matrix, "dwstream": up_matrix}
        else:
            gene_matrix[gene_id] = {"upstream": up_matrix, "dwstream": dw_matrix}

    return gene_matrix

sequence_hand = ps.FastaFile(fas_file)
variant_hand = ps.VariantFile(vcf_file, duplicate_filehandle=True)
alignment_hand = ps.AlignmentFile(bam_file)
interval_hand = ps.TabixFile(gtf_file, parser=ps.asGTF())

matrix_pool = make_matrix(interval_hand, sequence_hand, variant_hand, alignment_hand)

sequence_hand.close()
variant_hand.close()
alignment_hand.close()
interval_hand.close()


# Sequence is 0-based
# gonl-100a AC47H5ACXX-3-18 Example
# 1. get some example data from real dataset
# 1.1 example.fa
# reference genome: GRCh37
# (/groups/umcg-bios/tmp03/users/umcg-zzhang/projects/ASEPrediction/benchmark/inputs/references)
# ```
# $> head -668 genome.fa > tmp.fa
# $> grep -vn N tmp.fa
# $> (head -1 tmp.fa; sed -n '169,$p' tmp.fa) > example.fa
# $> module load SAMtools/1.5-foss-2015b
# $> samtools faidx example.fa
# example.fa example.fa.fai
# ```
# Now we have a fragment reference genome from GRCh37. It starts with non-N at
# 10,021 (167 * 60), ends at 40,020 (667 * 60), with length 30,000. (1:1-40020)
# 1.2 example.bam
# ```
# module load SAMtools
# ```
# 1.3 example.vcf.gz
# Fetch variants from gonl.chr1.snps_index.r5.3.vcf.gz
# /groups/umcg-gonl/prm02/releases/variants/GoNL1/release6.1/06_IL_haplotype_panel
# ```
# $> module load BCFtools/1.6.foss-2015b
# $> bcftools view gonl.chr1.snps_indels.r5.3.vcf.gz 1:40021-70020 > ~/Documents/example.vcf
# $> bgzip ~/Documents/example.vcf
# $> cd ~/Documents
# $> bcftools index example.vcf.gz
# ```

# 1.4 example.gff.gz
# Fetch interval from Homo_sapiens.GRCh37.75.gff
# ```
# grep -P "^1\t" Homo_sapiens.GRCh37.75.gff | sort -k4,5n > example.gff
# module load tabix
# bgzip example.gff
# tabix -p gff example.gff.gz
# awk '{if ($5 <= 9250800 && $1 == 1) {print}}' ../gff/Homo_sapiens.GRCh37.75.gtf  > example.gff
# ```