def convert_pdfs(articles_dir):

    import sys
    import os
    import re
    import urllib.request
    import subprocess
    import time

    # own files
    from pysci import convertpdf as pdf
    from pysci import docutils as du

    cermine_url = r'https://maven.ceon.pl/artifactory/kdd-releases/pl/edu/icm/cermine/cermine-impl/1.13/cermine-impl-1.13-jar-with-dependencies.jar'
    cermine_jar_local_path = 'cermine-impl-1.13-jar-with-dependencies.jar'

    # download the cermine jar to current dir
    filename, headers = urllib.request.urlretrieve(cermine_url, cermine_jar_local_path)

    # directory containing the PDFs to process
    articles_dir = articles_dir

    def convert_pdf_dir_to_xml(pdf_dir, verbose=True):
        output = subprocess.run([r"java", '-cp', cermine_jar_local_path, 'pl.edu.icm.cermine.ContentExtractor', 
                                 '-path', articles_dir], stdout=subprocess.PIPE).stdout
        result_string = output.decode('utf-8', 'ignore')
        result_output = result_string.splitlines() # using split('\r\n') gives empty str at end of list
        for line in result_output:
            if verbose:
                print(line)
        return result_output

    print("Processing pdfs in %s using Cermine..." %articles_dir)

    time1 = time.time()

    # convert all the pdfs
    output = convert_pdf_dir_to_xml(articles_dir, verbose=False)

    time2 = time.time()

    print("Done.")
    print("Conversion of all files in %s took %0.1fmin" %(articles_dir, (time2-time1)/60.0))

    # optionally: delete Cermine jar
    os.remove(cermine_jar_local_path)

    files_in = 0
    files_converted = 0

    print("Processing pdfs in %s using pdfminer..." %articles_dir)

    time1 = time.time()

    for root, dirs, files in os.walk(articles_dir):
        # ignore files that aren't pdf
        files[:] = [f for f in files if os.path.splitext(f)[1].lower() == du.PDF_extension]
        for filename_pdf in files:
            files_in += 1
            filepath_pdf = os.path.join(root,filename_pdf)
            filename_raw = du.remove_extension(filename_pdf)
            filename_txt = filename_raw + du.TXT_extension
            filepath_txt = os.path.join(root,filename_txt)
            if os.path.isfile(filepath_txt):
                #print("Skipping %s" %filepath_txt[:90])
                continue
            success = pdf.convert_pdf_to_text(filepath_pdf, filepath_txt, verbose=False)
            if success:
                print("Converted file %s" %filepath_txt[:90])
                files_converted += 1
            else:
                try:
                    os.remove(filepath_txt)
                except PermissionError as e:
                    print("PermissionError while trying to delete file %s" %filepath_txt[:90])
                
    print("We read in %s pdf files and output %s text files." %(files_in, files_converted))

    time2 = time.time()
    print('Conversion of all files in %s took %0.1fmin' %(articles_dir, (time2-time1)/60.0))


def extract_text(articles_dir):

    import os
    import pandas as pd
    import xml.etree.ElementTree as ET

    # own files
    from pysci import docutils as du
    from pysci import geoparse as gp

    articles_dir = articles_dir
    corpus_name = 'test-corpus'
    path_to_pickle = 'science_articles.pkl'

    documents = []  # list of ScienceDocs
    min_characters = 100

    count_pdf_files = 0
    count_txt_files = 0
    count_xml_files = 0

    for root, dirs, files in os.walk(articles_dir):
        # ignore files that aren't pdf
        files[:] = [f for f in files if os.path.splitext(f)[1] == du.PDF_extension]
        for filename_pdf in files:
            count_pdf_files += 1
            filepath_pdf = os.path.join(root,filename_pdf)
            filename_raw = du.remove_extension(filename_pdf)
            # create ScienceDoc object
            scidoc = du.ScienceDoc(corpus_name=corpus_name, file_name=filename_raw)
            documents.append(scidoc)
            
            ### PROCESS TXT ###
            filename_txt = filename_raw + du.TXT_extension
            filepath_txt = os.path.join(root,filename_txt)
            if os.path.isfile(filepath_txt):
                count_txt_files += 1
                scidoc.has_text = True
                with open(filepath_txt, 'r', encoding='utf-8') as f:
                    scidoc.raw_contents = f.read()
                    
                ### Detect methods sections and extract relevant text from TXT
                # here using regular expression for Orchards corpus, TXT
                section_titles_txt, relevant_text_txt = gp.extract_methods_text(scidoc.raw_contents, 
                                                                                re_to_match=gp.RE_ORCHARDS_METHODS_TEXT)
                print("Section titles text:")
                print(section_titles_txt)  # section titles in a list
                print("Relevant content text, length: %s" %len(relevant_text_txt))  # one single string
            else:
                print("No txt document for %s" %filename_raw)
                section_titles_txt = []
                relevant_text_txt = ''
                
            ### PROCESS XML ###
            filename_xml = filename_raw + du.XML_extension
            filepath_xml = os.path.join(root,filename_xml)
            if os.path.isfile(filepath_xml):
                count_xml_files += 1
                # defaults to False in class
                scidoc.has_xml = True
                tree = ET.parse(filepath_xml)
                xml_root = tree.getroot()
                scidoc.xml_root = xml_root
                # Extract info directly from XML
                scidoc.title = du.get_article_title(xml_root)
                scidoc.year = du.get_publication_year(xml_root)
                scidoc.journal = du.get_journal_title(xml_root)
                scidoc.xml_contents = du.extract_content_text(xml_root)
                scidoc.authors, scidoc.affiliations = du.get_article_authors_affiliations(xml_root)
                scidoc.countries = du.get_affiliation_countries(xml_root)
                
                ### Detect methods sections and extract relevant text from XML
                # here using regular expression for Orchards corpus, XML
                methods_content_xml = gp.extract_methods_xml(scidoc.xml_root, re_to_match=gp.RE_ORCHARDS_METHODS_HEADINGS)
                section_titles_xml = [item[0] for item in methods_content_xml]  # a list
                relevant_text_list_xml = [item[1] for item in methods_content_xml]  # a list
                relevant_text_xml = '\n\n'.join(txt for txt in relevant_text_list_xml)
                print("Section titles xml:")
                print(section_titles_xml)
                print("Relevant content xml, length: %s" %len(relevant_text_xml))
            else:
                print("No xml document for %s" %filename_raw)
                section_titles_xml = []
                relevant_text_xml = ''
                
            ### Continue with XML or TXT? ###
            # use XML content unless:
            #   - we found no relevant headings in XML, or
            #   - we have insufficient content in the XML text portions
            use_xml = True
            if (len(section_titles_xml) == 0) or (len(relevant_text_xml) < min_characters):
                use_xml = False

            print("Using XML: %s" %use_xml)
            scidoc.use_xml = use_xml
            section_titles = []
            relevant_text = ''
            if use_xml:
                scidoc.methods_sections = section_titles_xml
                scidoc.relevant_text = relevant_text_xml
            else:
                scidoc.methods_sections = section_titles_txt
                scidoc.relevant_text = relevant_text_txt
                
    print("We have %s ScienceDocs." %len(documents))
    print("We have %s pdf documents." %count_pdf_files)
    print("We have %s txt documents." %count_txt_files)
    print("We have %s xml documents." %count_xml_files)

    # serialize the ScienceDocs for ease of use in the next step
    du.pickle_data(documents, path_to_pickle)


def identify_and_filter_locations():

    import os
    import re
    import pandas as pd

    import nltk
    import nltk.data
    from nltk.tag import StanfordNERTagger
    # nltk customization
    nltk.data.path.append('data_NLTK')
    StanfordBaseDir = ''
    os.environ['CLASSPATH'] = StanfordBaseDir + 'data_NER/stanford-ner-2020-11-17/'
    os.environ['STANFORD_MODELS'] = StanfordBaseDir + 'data_NER/stanford-ner-2020-11-17/classifiers'
    os.environ['JAVAHOME'] = 'C:/Program Files/Java/jre1.8.0_351/bin/java.exe'
    # nltk initialization of Stanford NER tagger
    tagger = StanfordNERTagger('english.all.3class.distsim.crf.ser.gz')

    # own files
    from pysci import docutils as du
    from pysci import geoparse as gp

    path_to_pickle = 'science_articles.pkl'
    # if needed, re-serialize in addition to any CSV export
    path_to_repickle = 'science_articles_geoparsed.pkl'

    # load the serialized ScienceDocs
    science_docs = du.load_data(path_to_pickle)

    # start from the ScienceDoc instances
    for scidoc in science_docs:
        print("\n### Processing article %s..." %scidoc.file_name)

        ### PARSE TITLE FROM XML ###
        if scidoc.has_xml:
            if scidoc.title:
                scidoc.title_locations = []
                title_string = scidoc.title
                #print("Title: %s" %title_string)
                # process title
                title_clean = gp.multireplace(title_string)
                sent_tok = nltk.word_tokenize(title_clean)
                sent_pos = nltk.pos_tag(sent_tok)
                sent_ner = tagger.tag(sent_tok)
                # customizable extract method
                extracted_chunks = gp.extract_chunks_from_sentence(
                    sent_ner, include_cardinal=True, include_other_spatial=True, include_types=True)
                if extracted_chunks:
                    print("### Found %s location candidates in title:" %len(extracted_chunks))
                    for loc_chunk in extracted_chunks:
                        loc_chunk_str = gp.tuple_list_to_string(loc_chunk)
                        print("\t%s" %loc_chunk_str)
                    extracted_chunks_pos = gp.filter_chunk_candidates(sent_tok, extracted_chunks, verbose=True)
                    print("### Kept %s location chunks in title:" %len(extracted_chunks_pos))
                    for loc_chunk_keep in extracted_chunks_pos:
                        loc_chunk_keep_str = gp.tuple_list_to_string(loc_chunk_keep)
                        # keep just the final filtered locations - empty list means we had none
                        scidoc.title_locations.append(loc_chunk_keep_str)
                        print("\t%s" %loc_chunk_keep_str)
            else:
                #print("No title for this article.")
                scidoc.title_locations = gp.NO_TITLE_STRING  
        else:
            #print("No xml file for this article.")
            scidoc.title_locations = gp.NO_XML_STRING

        ### Process article contents
        content_locations = []
        content_locations_filtered = []
        location_sentences = []
        for par in re.split('[\n]{2,}', scidoc.relevant_text):
            par_clean = gp.multireplace(par)
            #print("Clean paragraph: %s" % (par_clean))
            sentences = nltk.sent_tokenize(par_clean)
            for sent in sentences:
                sent_added = False
                sent_tok = nltk.word_tokenize(sent)
                sent_pos = nltk.pos_tag(sent_tok)
                sent_ner = tagger.tag(sent_tok)
                # customizable extract method
                extracted_chunks = gp.extract_chunks_from_sentence(
                    sent_ner, include_cardinal=True, include_other_spatial=True, include_types=True)
                if extracted_chunks:
                    #print("NER tagged sentence:\n %s" %sent_ner)
                    print("### Found %s location candidates in sentence:" %len(extracted_chunks))
                    for loc_chunk in extracted_chunks:
                        loc_chunk_str = gp.tuple_list_to_string(loc_chunk)
                        content_locations.append(loc_chunk_str)
                        print("\t%s" %loc_chunk_str)
                    extracted_chunks_pos = gp.filter_chunk_candidates(sent_tok, extracted_chunks, verbose=True)
                    print("### Kept %s location chunks:" %len(extracted_chunks_pos))
                    for loc_chunk_keep in extracted_chunks_pos:
                        loc_chunk_keep_str = gp.tuple_list_to_string(loc_chunk_keep)
                        content_locations_filtered.append(loc_chunk_keep_str)
                        print("\t%s" %loc_chunk_keep_str)
                        if not sent_added:
                            sent_no_breaks = sent.replace('\n', ' ')
                            location_sentences.append(sent_no_breaks)
                            sent_added = True
                
        scidoc.content_locations = content_locations
        scidoc.content_locations_filtered = content_locations_filtered
        scidoc.location_sentences = location_sentences
        
    print("\n### Done.")
                

    # optionally repickle article data with locations etc
    du.pickle_data(science_docs, path_to_repickle)

    # flatten each list entry to a string instead of a list
    filenames_for_df = []
    use_xml_for_df = []
    methods_for_df = []
    titles_for_df = []
    title_locations_for_df = []
    content_locations_for_df = []
    content_locations_filtered_for_df = []
    location_sentences_for_df = []
    for doc in science_docs:
        filenames_for_df.append(doc.file_name)
        use_xml_for_df.append(doc.use_xml)
        try:
            titles_for_df.append(doc.title)
        except AttributeError:
            titles_for_df.append(gp.NO_TITLE_STRING)
        if doc.title_locations == gp.NO_XML_STRING or doc.title_locations == gp.NO_TITLE_STRING:
            title_locations_for_df.append(doc.title_locations)
        else:
            title_locations_for_df.append('; '.join([x for x in doc.title_locations]))
        try:
            methods_for_df.append(doc.methods_sections)
        except AttributeError:
            methods_for_df.append('')
        if not doc.content_locations:
            content_locations_for_df.append('')
        elif doc.content_locations == gp.NO_METHODS_STRING:
            content_locations_for_df.append(doc.content_locations)
        else:
            content_locations_for_df.append('; '.join([x for x in doc.content_locations]))
        if not doc.content_locations_filtered:
            content_locations_filtered_for_df.append('')
        elif doc.content_locations_filtered == gp.NO_METHODS_STRING:
            content_locations_filtered_for_df.append(doc.content_locations_filtered)
        else:
            content_locations_filtered_for_df.append('; '.join([x for x in doc.content_locations_filtered]))
        if not doc.location_sentences:
            location_sentences_for_df.append('')
        else:
            location_sentences_for_df.append(doc.location_sentences)

    df_geoparsed = pd.DataFrame({'filename_only':filenames_for_df, 
                                'use_xml':use_xml_for_df,
                                'title':titles_for_df,
                                'title_locations':title_locations_for_df,
                                'methods_sections':methods_for_df,
                                'content_locations':content_locations_for_df,
                                'content_locations_filtered':content_locations_filtered_for_df,
                                'location_sentences':location_sentences_for_df})

    # increase the column width display of pandas tables to view full cells
    #pd.options.display.max_colwidth = 500

    df_geoparsed.head()

    df_geoparsed.to_csv(os.path.join('results', 'articles_geoparsed.tsv'), sep='\t', index=False, quotechar='"', encoding='utf-8')

    # now each list item (each final content location) will be a separate row in the df
    filenames_flat = []
    content_locations_filtered_flat = []
    location_sentences_flat = []
    use_xml_flat = []
    for doc in science_docs:
        # Include title locations (Modified from E. Achesons Version)
        for location in doc.title_locations:
            content_locations_filtered_flat.append(location)
            location_sentences_flat.append('TITLE LOCATION')
            use_xml_flat.append(doc.use_xml)
            filenames_flat.append(doc.file_name)

        if not doc.content_locations_filtered:
            # store the 'no location' case!
            content_locations_filtered_flat.append(gp.NO_LOCATIONS_STRING)
            location_sentences_flat.append(gp.NO_LOCATIONS_STRING)
            use_xml_flat.append(doc.use_xml)
            filenames_flat.append(doc.file_name)
            continue
        elif doc.content_locations_filtered == gp.NO_METHODS_STRING:
            content_locations_filtered_flat.append(gp.NO_METHODS_STRING)
            location_sentences_flat.append(gp.NO_METHODS_STRING)
            use_xml_flat.append(doc.use_xml)  # we store 'N/A' already
            filenames_flat.append(doc.file_name)
        else:
            for location in doc.content_locations_filtered:
                content_locations_filtered_flat.append(location)
                use_xml_flat.append(doc.use_xml)
                filenames_flat.append(doc.file_name)
                found_sentence = False
                for sentence in doc.location_sentences:
                    if location in sentence:
                        found_sentence = True
                        location_sentences_flat.append(sentence)
                        break
                if not found_sentence:
                    location_sentences_flat.append('no exact sentence match')

    df_flat = pd.DataFrame({'filename':filenames_flat,
                            'content_locations':content_locations_filtered_flat,
                            'use_xml':use_xml_flat,
                            'location_sentences':location_sentences_flat})

    df_flat.head()

    df_flat.to_csv(os.path.join('results', 'locations.tsv'), sep='\t', index=False, quotechar='"', encoding='utf-8')


def clean_and_geocode_locations(api_key):

    import os
    import re
    import pandas as pd

    # own files
    from pysci import docutils as du
    from pysci import geoparse as gp
    from pysci import geocode as gc

    path_to_content_locations = os.path.join('results', 'locations.tsv')
    df_locations = pd.read_csv(path_to_content_locations, sep='\t', quotechar='"', encoding='utf-8')
    df_locations.head()

    # create googlemaps.Client object: you will need an API key for this!
    gmaps = gc.create_google_geocoder(api_key=api_key)
    # cache so we don't re-query identical strings
    local_cache_google = {}
    # or load existing cache
    #local_cache_google = du.load_data('local_cache_google.pkl')
    #print("The cache has values for %s string keys." %len(local_cache_google))

    loc_clean = []
    loc_lats = []
    loc_lons = []
    loc_strings = []
    loc_types = []

    for content_location in df_locations['content_locations'].tolist():
        if content_location == gp.NO_METHODS_STRING or content_location == gp.NO_LOCATIONS_STRING:
            # don't geocode these but store placeholder strings
            loc_clean.append(content_location)
            loc_lats.append(content_location)
            loc_lons.append(content_location)
            loc_strings.append(content_location)
            loc_types.append(content_location)
            continue
        clean_text = gc.clean_for_geocode(content_location)
        loc_clean.append(clean_text)
        #print("\tgeocoding text: %s" %clean_text)
        top = gc.geocode_with_cache_google(clean_text, gmaps, local_cache_google)
        if top:
            # get point
            geometry = top['geometry']
            pt = geometry['location']
            # store stuff
            loc_lats.append(pt['lat'])
            loc_lons.append(pt['lng'])
            loc_strings.append(top['formatted_address'])
            loc_types.append(geometry['location_type'])
        else:
            #print("\tWe had no top result")
            loc_lats.append(gc.NO_RESULT_STRING)
            loc_lons.append(gc.NO_RESULT_STRING)
            loc_strings.append(gc.NO_RESULT_STRING)
            loc_types.append(gc.NO_RESULT_STRING)

    print("Done.")

    # repickle the cache at the end...
    print("The cache now has values for %s string keys." %len(local_cache_google))
    du.pickle_data(local_cache_google, 'local_cache_google.pkl')

    df_locations['clean_content_loc'] = loc_clean
    df_locations['geocode_lat'] = loc_lats
    df_locations['geocode_lon'] = loc_lons
    df_locations['geocode_str'] = loc_strings
    df_locations['geocode_type'] = loc_types
    df_locations.head()

    cols_in_order = ['filename', 'content_locations', 'clean_content_loc', 'geocode_str', 'geocode_type', 
                     'geocode_lat', 'geocode_lon', 'use_xml', 'location_sentences']
    df_locations_clean = df_locations.loc[:,cols_in_order]
    # export to file
    df_locations_clean.to_csv(os.path.join('results', 'locations_geocoded.tsv'), sep='\t', index=False, quotechar='"', encoding='utf-8')

######################################

def map_results():

    import pandas as pd
    import folium
    import os

    df_results = pd.read_csv(os.path.join('results', 'locations_geocoded.tsv'), sep='\t', quotechar='"', encoding='utf-8')
    df_results

    df_geocoded = df_results[pd.to_numeric(df_results.geocode_lat, errors='coerce').notnull()].copy()
    df_geocoded['lat_float'] = df_geocoded['geocode_lat'].astype(float)
    df_geocoded['lon_float'] = df_geocoded['geocode_lon'].astype(float)

    # function to show a text value for the geocode result, if present
    def geocode_eval_to_text(geocode_eval):
        if geocode_eval == '1.0':
            return 'correct'
        elif geocode_eval == '0.0':
            return 'incorrect'
        elif geocode_eval == 'nan':
            return 'upstream error'
        else:
            return geocode_eval

    # function to decide what goes in a map popup
    def to_html_string(row):
        html = "geocoded string: " + str(row['clean_content_loc']) + "<br>"
        html += "result string: " + str(row['geocode_str']) + "<br>"
        html += "result point: " + str(row['geocode_lat']) + ", " + str(row['geocode_lon']) + "<br>"
        html += "result type: " + str(row['geocode_type']) + "<br>"
        #html += "geoparse eval: " + str(row['eval_geoparse']) + "<br>"
        #if str(row['error_analysis']) != 'nan':
        #    html += "error: " + str(row['error_analysis']) + "<br>"
        #html += "geocode eval: " + geocode_eval_to_text(str(row['eval_geocode'])) + "<br>"
        #html += "full pipeline eval: " + str(row['eval_full_pipeline'])
        return html

    # show the TP/FP in different colors, if evaluated
    def get_color(evaluation):
        if evaluation == 'TP':
            # blue
            return '#3186cc'
        elif evaluation == 'FP':
            # red
            return '#cc0000'
        else:
            # we had a different value than TP or FP
            return '#cc0000'

    country_geojson_url = 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_110m_admin_0_countries.geojson'

    result_map = folium.Map(tiles=None, location=[30, 0], zoom_start=2)
    folium.GeoJson(
        country_geojson_url,
        style_function=lambda feature: {
            'fillColor': 'white',
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.7,
        }
    ).add_to(result_map)
    result_map

    for index, row in df_geocoded.iterrows():
        lat = row['lat_float']
        lon = row['lon_float']
        html_for_popup = folium.Html(to_html_string(row), script=True)
        html_popup = folium.Popup(html_for_popup, max_width=400)
        folium.CircleMarker([lat,lon], 
                        radius=5,
                        popup=html_popup,
                        color=get_color('TP'),  # unevaluated
                        fill_color=get_color('TP'),  # unevaluated
                       ).add_to(result_map)
    result_map

    # export map to an html file!
    result_map.save(os.path.join('maps', 'demo_result_map.html'))

    return result_map