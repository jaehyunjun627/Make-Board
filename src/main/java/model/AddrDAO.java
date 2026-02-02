package model;

import java.util.ArrayList;
import java.util.List;

public class AddrDAO {

	private String username;
	private String password;

	public AddrDAO() {
	}

	List<AddrDTO> addrlist = new ArrayList<AddrDTO>();

	public void add(AddrDTO ab) {
		addrlist.add(ab);

	}

	public List<AddrDTO> getAddrlist() {
		return addrlist;
	}

	public AddrDTO getadd(String username) {
		for (AddrDTO ab : addrlist) {
			if (ab.getUsername().equals(username)) {	
				return ab;
			}

		}
		return null;

	}

}